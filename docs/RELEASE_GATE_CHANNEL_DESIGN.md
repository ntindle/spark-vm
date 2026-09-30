# Fleet→box release-gating channel — transport design (G18 / #609)

The rollout controller (G15, `ROLLOUT_CONTROLLER_DESIGN.md`) assigns waves,
health-gates promotion, and flips an emergency freeze. The inventory (G16)
remembers what each box runs; the event vocabulary (G17) reports what
happened. But nothing in the fleet layer can *reach a box*: both per-box
updaters are autonomous timer loops — `deploy/auto-deploy.sh` fires every
10 minutes (`deploy/auto-deploy.timer`, `OnUnitActiveSec=10min`), the
toolset updater weekly (`deploy/sparkvm-toolset-update.timer`, Sun 03:00
box-local + 30min jitter) — with no external gate. A wave assignment that
never reaches the box is a spreadsheet; a freeze switch that cannot beat
the 10-minute tick is theater (#609).

G15's design stated the *interface* the controller needs (§5 of that doc):
the box asks "for my box_id, what is the newest commit I may converge to,
and is the fleet frozen?", the hook polls on a 60–120s cadence decoupled
from the update tick, the tick re-checks immediately before any deploy,
answers are signed/pinned to the controller's provisioned identity, and a
box that cannot reach the controller behaves as frozen. It left the
*transport* to G18. This doc is that design: how the answer travels from
the controller to the box — and the latency, trust, and failure semantics
that make it real.

Scope note (both-supported default, per PLAYBOOK): the channel is a repo
component the self-hosted operator's own N-box estate runs today, and the
hosted product reuses it for tenant fleets. The operator estate is the S1
slice; the tenant-fleet instantiation additionally waits on G13 attestation
and H11 — and §6 says why.

## 1. The transport decision

#609 names three candidate mechanisms:

1. **Boxes pull controller-published release state before each tick.**
2. The controller pushes/invokes updates.
3. The controller manages per-box timer enablement.

**G18 picks (1): pull of a controller-signed, short-TTL gate document —
`gate.json` — over the operator's SSH path to the boxes.** Not a new
protocol, not a new listener:

- **Push is rejected**: it needs an inbound listener on every box — a new
  attack surface that contradicts the "no new inbound port, no control
  plane" discipline G16 S1 established for the operator estate, and it
  inverts the trust direction: the box would have to accept deploy
  instructions from whoever can reach its socket. An unsigned "update now"
  is a remote-code-execution primitive (G15 §5); a *pushable* one is that
  primitive with a network address.
- **Timer enablement is rejected**: it is too coarse to express "hold this
  release, take the next one", it fights the box's autonomy model (the
  tick owns scheduling; the gate owns permission), and a disabled timer
  cannot be honestly reported by the box — `fleet status` would show a
  healthy fleet while boxes silently missed their windows. The gate answers
  a question, not a command; the timer stays the box's.
- **Pull composes with connectivity the operator already has.** The
  operator's estate is reachable over SSH — that is the whole premise of
  the both-supported story. One honest correction to the framing: G16 S1
  as *shipped* does not yet run a standing SSH cron (`fleet/README.md`
  gathers artifacts into a local estate dir by hand or rsync; live SSH
  pull is a later collector slice, per the G16 implementation note). So
  G18's S1 does not "extend the existing cron" — it *ships the deliver
  step*: a documented operator sync loop that `scp`s the signed `gate.json`
  to each box. G15's S1 paragraph ("the local mirror the operator's cron
  syncs … the first instantiation of the G18 channel") named the shape;
  this doc makes the loop itself a deliverable, not an assumption.

## 2. The gate document

One fleet-wide document, `gate.json`, published by the controller. Not
per-box: the box self-evaluates its answer from its `box_id` (which it
already knows for G16) against the document's wave assignment. One
document is O(1) to distribute, idempotent to sync, and carries no
per-box secrets.

```json
{
  "schema_version": 1,
  "issued_at": "2026-09-29T23:04:11Z",
  "ttl_seconds": 600,
  "key_id": "ctl-2026-09",
  "freeze": false,
  "releases": {
    "repo":    { "max_permitted_commit": "9ddbc34e44bec7cacf5ab3c75cb184b2714de0a1", "channel": "stable" },
    "toolset": { "max_permitted_pin": "2026.09.27",                                  "channel": "stable" },
    "image":   { "max_permitted_image_version": "2026.09.29-0",                      "channel": "stable" }
  },
  "waves": {
    "repo":    { "live": 2, "state": "wave-2", "assignments": { "box-07": 1 }, "default": "hash_mod_4" },
    "toolset": { "live": 1, "state": "canary", "assignments": { "box-07": 1 }, "default": "hash_mod_4" }
  },
  "hmac": "sha256-hex-of-canonical-body"
}
```

Field semantics:

- **`issued_at` + `ttl_seconds`**: the document is a *lease*, not a
  decree. A box treats a missing, malformed, bad-MAC, or expired document
  as **no-signal → frozen** (G15 §5 fail-closed). TTL is 600s in S1 — long
  enough to ride out sync *jitter*, and deliberately *not* a full
  missed sync: with the operator loop configured at ≤ TTL/2 (≤5 min), a
  missed loop expires the document by design, and the fleet freezes
  loudly (§4). The honest corollary: **the S1 freeze-latency bound is
  §4's two-part contract — delivery within sync_cadence, effectuation
  within sync_cadence + tick_interval** — not the hook cadence alone; §4
  states the operator's sync cadence as part of the contract, so the bound
  is a configured property, not an assumed one.
- **`releases`**: the *per-component* max-permitted versions — the
  registry entries (G15 §2) the fleet may converge to. Unregistered
  commits never deploy on fleet-managed boxes (G15 §5's honest corollary:
  merge-to-main *and* register-to-deploy). Components: `repo` (commit the
  box-side repo updater may converge to), `toolset` (pin the weekly
  updater may converge to — waves never force a mid-week run, G15 §5),
  `image` (the reimage approval for tenant boxes, G15 §5's last paragraph:
  the wave gate authorizes reimages, not in-place updates).
- **`waves`**: per component, which wave is live and the assignment.
  `default: "hash_mod_4"` is G15 §2's deterministic default (`hash(box_id)
  mod buckets`); `assignments` pins the exceptions (canary boxes, boxes
  that must never be in wave 1). `state` uses G15 §3's rollout state names
  (`draft`/`canary`/`wave-N`/`complete`/`halted`); `freeze: true` at the
  document top level is orthogonal and release-independent (G15 §3).
- **`key_id`**: which controller key signed this document, so key rotation
  is a document field, not a flag day (§5).
- **`hmac`**: HMAC-SHA256 over the canonical body (keys sorted, UTF-8),
  using the controller key provisioned to the box at install time (the
  "pinned in operator-deployed config" of G15 §5). Symmetric, stdlib-only
  (`hashlib`/`hmac`) — no new crypto dependency on the box, no asymmetric
  key parsing in shell or stdlib Python. S3's hosted instantiation keeps
  the same field with the control plane's key on the scheduler-side path
  (§6).

The document names *no* merge rights, no operator identities, no secrets —
it is a signed permission, safe to transit through the operator's existing
file-sync.

## 3. The box-side hook

`fleet/gate_query.py` (stdlib only) — the contract both updaters call:

```
gate_query.py --component repo --box-id <id> [--gate-file <path>]
```

Reads the local `gate.json` (default `/var/lib/sparkvm/gate/gate.json`,
overridable), verifies the HMAC against the provisioned controller key,
evaluates, and prints one machine-readable line:

```
state=<permitted|frozen|stale|no-signal> [permitted=<v>] reason=<token> age=<s>
```

Evaluation order, per (box, component):

1. No file / unreadable / bad MAC / unknown key_id → `state=no-signal`
   (reason `gate-unreachable`).
2. `now - issued_at > ttl_seconds` → `state=stale` (reason `gate-expired`).
3. `freeze: true` → `state=frozen` (reason `fleet-freeze`).
4. Component's wave not yet live for this box → `state=frozen` (reason
   `wave-not-live`).
5. Otherwise → `state=permitted permitted=<max-permitted>` (reason
   `wave-<n>`).

**Enforcement point.** The update tick's re-query — immediately before
any deploy — is the enforcement point. The 60–120s hook loop (a small
timer unit next to the updaters, an S1b deliverable) is the latency
optimizer and the local-status writer: it keeps the answer fresh so the
tick's check is cheap and so `fleet status` can show "gate-stale (last
good answer T ago)". A tick that starts after a freeze is published but
before the new document reaches the box may still deploy — §4's bound
covers exactly this race: the delivery bound is the window in which it
can happen, and effectuation completes at publish + sync_cadence +
tick_interval.

**Hook points (the S1 enforcement):**

- `deploy/auto-deploy.sh`'s `pending_range()` (line ~1018): the blocked-
  commit logic runs on the *true* `origin/main` head first (a capped `new`
  would otherwise misread a wave hold as "history rewritten" and wedge
  the block forever); the gate cap applies only to the emitted range —
  `new` is capped at `min(origin/main head, permitted)`. If `permitted ≤
  watermark` (freeze after convergence, wave reassignment), the range is
  inverted and `pending_range` returns 1 instead of emitting garbage.
  The `permitted` value gets the same fail-loud SHA discipline as the
  range ends: a malformed commit is `no-signal`, not a return-2 alert
  storm. On `state=frozen|stale|no-signal` it returns 1 — nothing to do —
  with a log line naming the reason token (never a secret, never the key).
  The forced-deploy scan (extra-inputs) stands down under the same answer:
  a frozen fleet deploys nothing, including component redeploys the
  forced path would otherwise trigger. This preserves every existing
  behavior (watermark, blocked-commit, fail-loud SHA checks); the gate
  only *caps* the target.
- `deploy/toolset-update.sh`: `_read_pin`'s target is capped by the hook's
  `max_permitted_pin` the same way. Pins are version strings, not commits,
  so `min()` is lexicographic comparison on the date-pin format — say so
  in the code comment, not just here. A frozen fleet holds toolset pins
  exactly like repo commits (G15 §5).
- The hook loop writes the last answer to the box's local status file —
  G15 §5's "gate-answer age/source" — so `fleet status` shows stale as
  *visible* degraded operation, never silent drift. G16's collector reads
  that status file as an S2 artifact (composition, §7); S1 ships without
  touching the inventory record schema.

**Log shapes and the G17 vocabulary.** The hook's log lines use the
outcome vocabulary G17 §2 already reserved for this design: `fleet-freeze`
/ `wave-not-live` → `skipped-frozen` ("the G18 gate said frozen"),
arc deferral → `deferred-arc`. Both are S2/S3-forward outcomes — the S1
canonicalizer does *not* infer events from gate silence (G17 §3's
collector discipline: never infer `noop` from silence); `no-signal` and
`gate-expired` produce no event, only the local status line. Gate
staleness visibility belongs to the inventory's gate answer-age field
(G16 §4), and the fifth fleet alert rule (§7) reads the collector, not
the event stream — a partitioned box emitting freeze-shaped events would
make the G17 §5 freeze-propagation proof unprovable.

Arc-awareness (never-interrupt-an-arc, G15 §6/G11): the hook reports
permission, not timing — a box with an active arc *defers* its permitted
update until the arc ends. The deferral is emitted as `deferred-arc`, so
the controller's gates see a deferral, not a failure.

## 4. The S1 distribution path and its latency contract

S1 adds **no daemon, no listener, no control plane** — but it does add
one real deliverable: the operator sync loop. A documented script (shipped
in the S1 slice, run from the operator's own cron) iterates the estate's
box list and `scp`s the freshly published `gate.json` to each box's
`/var/lib/sparkvm/gate/`. The controller side is `fleet/gate_publish.py`:
reads the release registry + wave manifest + freeze flag, emits the
signed `gate.json` the loop distributes.

The latency contract, stated honestly, in two parts — because the
tick-time query is the enforcement point (§3):

- **Delivery**: the box holds the frozen document within **sync_cadence**
  of publish (≤5 min in S1's reference numbers). No `hook_interval` term
  here — the hook loop (S1b) is the latency optimizer and status writer,
  not the delivery path.
- **Effectuation**: a freeze published at t0 stops the fleet by t0 +
  **sync_cadence + tick_interval**. A tick that starts after publish but
  before the document arrives may still deploy — that race is inherent to
  pull, and the delivery bound is exactly the window in which it can
  happen. For the 10-min auto-deploy tick: a freeze is fully effective
  within ~15 min of publish. The toolset's weekly tick is trivially
  covered.
- The operator configures the sync loop at **≤ TTL/2**; the hook refuses
  the document past TTL (600s in S1). The TTL rides out *jitter*, not a
  full missed sync — a missed 5-minute loop means the document expires by
  design, and the fleet freezes *loudly* (gate-stale on `fleet status`)
  rather than releasing itself. This is the fail-closed direction G15 §5
  chose: a broken sync loop is a visible incident, not a silent rollout.
- The contract is per-estate: larger estates (slower sync fan-out) get a
  longer stated bound, not a shorter assumed one. The design names the
  bound; the operator's cron owns it.

## 5. Keys, rotation, and the trust root

- **Provisioned material: the controller MAC key + the box's `box_id`.**
  Both are pinned in operator-deployed config on each box (file mode 0600,
  root-owned). The `box_id` is what §2's self-evaluation needs: G16's S1
  collector reads box identity from the *operator's* mapping (no box-side
  `box_id` exists today — `auto-deploy.sh` carries none), so G18's
  install step writes the mapping's entry onto the box alongside the key.
  Without this the core mechanism cannot run; the design says so instead
  of assuming it.
- **One fleet-shared MAC key — stated without varnish.** HMAC is
  symmetric: there is no verify-only key, and every box holds the fleet
  *signing* key. The earlier draft's "cross-box forgery requires the
  controller key itself, which lives on the operator's machine" was
  wrong — a root-compromised box *can* mint fleet-valid documents for
  other boxes. The actual cross-box barrier is **delivery-path
  ownership**: the only writer of a box's `/var/lib/sparkvm/gate/` is the
  operator's sync loop; a forged document never reaches another box
  unless the sync path is compromised too. Say it plainly: the MAC stops
  on-path tampering and misconfiguration, not a rooted fleet member.
- **Compromise response is rotate-and-reprovision.** `key_id` in the
  document names which controller key signed it; the box's config may hold
  two keys (current + next) during a rotation window, and the hook accepts
  either, logging which verified. Rotation is: provision the next key to
  all boxes (the sync loop already reaches them), publish with the new
  `key_id`, retire the old after TTL × 2. No flag day, no fleet-wide
  restart. The honest limit: dual-accept *bounds* the rotation window —
  a compromised-but-not-yet-reprovisioned box keeps a valid key through
  it. Rotation must therefore be paired with re-provisioning, not treated
  as revocation.
- **Threat the MAC answers** (G15 §5): an unsigned "update now" is a
  remote-code-execution primitive. The MAC binds permission to the
  controller's identity for the on-path attacker; for the rooted box, the
  trust story is delivery-path ownership plus rotation, stated above. For
  tenant fleets, S3's scheduler-facing channel (§6) removes the box from
  the equation entirely — which is what closes the self-forge, per G13's
  threat model ("a tenant Muse with shell on the box").

## 6. Tenant-fleet instantiation (S3 — waits on G13 + H11)

The operator estate runs S1 today. The hosted tenant fleet reuses the
same document schema and the same controller, with the channel made
**scheduler-facing** — because G13 §3 T1 requires it: *"on tenant boxes
the wave gate applies to reimage *approval* consumed by the scheduler,
not by the box … a tenant box polling anything learns nothing actionable
and changes nothing. G18's transport design must keep it that way."* An
earlier draft served the document to the box over the box→plane dial-out
and ran the same hook there; that was box-facing by construction and is
withdrawn.

- **Transport**: the *scheduler* fetches the per-tenant gate document
  over the control-plane-internal path. The box-side hook does not run
  on tenant boxes; the box's dial-out carries events and inventory, not
  the gate. The self-forge is closed the way G13 closes it: there is
  nothing on the box to forge — the permission decision lives in the
  scheduler, which the tenant cannot reach (G13 §3 T1).
- **Authority** (G13's question — who may hold/release a tenant's box):
  release registration and freeze/unfreeze are *operator* actions on the
  control plane. There is **no tenant consent gate** — G13 §1 excludes
  the tenant Muse from all update authorization ("it cannot trigger,
  schedule, defer, veto, or approve a reimage"; T4: "No consent gate
  exists"), because consent-gated updates re-create the consent surface
  the reimage decision deliberately avoided. The tenant's holds are the
  ones G13 grants: arc-deferral (never-interrupt-an-arc) and visibility.
  Waves scope per tenant (H11); the gate document is per-tenant in the
  hosted instantiation.
- **Attestation** (G13 §3 T2) governs the *event* direction, not the gate
  direction: gates consume only box-identity-attested G17 events, so a
  tenant forging `succeeded` events cannot promote a bad release. T2 was
  never a rule about serving documents to boxes, and this design does not
  cite it as one.

The never-interrupt-an-arc and suspended-box (G14) constraints apply
unchanged: the scheduler schedules around arcs; suspended boxes are
evaluated on wake against the *current* permitted version.

## 7. Composition with the sibling designs

- **G15 (controller)**: this doc delivers §5's "G18 decides the
  transport". The controller's S1 "interim transport" paragraph (Build
  slices → S1 of that doc) is this design's S1; no re-litigation — the
  mirror *is* `gate.json` with the issuance timestamp and short TTL that
  doc required, and the deliver loop is now a named deliverable rather
  than an assumed cron.
- **G16 (inventory)**: the hook's local status file (answer + age +
  source) is a future collect artifact (S2); S1 ships without touching
  the inventory record schema.
- **G17 (events)**: the hook's log shapes get S2 mapping rows in the
  outcome vocabulary G17 §2 already reserved for this design —
  `skipped-frozen` ("the G18 gate said frozen") for `fleet-freeze` /
  `wave-not-live`, `deferred-arc` for arc deferral. The S1 canonicalizer
  infers nothing from gate silence (G17 §3's collector discipline);
  `no-signal` / `gate-expired` produce no event. The four fleet alert
  rules (UPDATE_EVENT_REPORTING §4 S1) gain a fifth: **correlated
  gate-stale across boxes** — a fleet-wide sync outage is a fleet
  incident, and it pages as one. The rule is specified here and reads
  the collector's gate answer-age field (not the event stream); it is
  folded into UPDATE_EVENT_REPORTING's S1 alert set when the S1b slice
  lands (pointer comment on #608 at ship).
- **G11–G14**: the `image.max_permitted_image_version` field is the wave
  gate's reimage approval (G15 §5); the `maintenance` code's enter/exit
  stays scheduler-owned (UPDATE_CHANNEL_POLICY.md producer rule); the
  session-clock freezes (UPDATE_IDLE_SUSPEND_CLOCK.md D1) apply during
  gate-held reimages exactly as during any maintenance window.

## 8. Deliberately out of scope

- **Concurrent releases**: the document carries one live wave per
  component. G15's open question 1 (stable wave-2 while security canary
  soaks) reappears here as a schema question — S1 says one; the security
  channel's compressed waves ride the same document.
- **N=1 estates**: the per-box updaters suffice (G15 §9). A single box
  with a gate document that always says "permitted" is ceremony, not
  safety — the hook is inert unless the operator publishes.
- **What the waves are** (G15): decided there; this decides how they
  travel.
- **The controller's own availability**: the design is explicit that the
  controller is a single point of *update* failure — controller down
  means the whole fleet holds, including the security channel (G15 §5).
  S3 may add a hot-standby publisher; S1 does not.

## Build slices

- **S1a — the acceptance sketch (ship first):** `fleet/gate_publish.py`
  (controller side: registry + manifest + freeze → signed `gate.json`),
  `fleet/gate_query.py` (box side: verify + answer), the operator sync
  loop (the documented deliver step), the `pending_range()` cap on the
  repo updater — and the **freeze-drill test**: publish a freeze, measure
  wall-clock until every box in a 2-box fixture reports `state=frozen`
  from `gate_query.py`, assert ≤ `sync_cadence + ε` (the harness polls
  `gate_query.py` on its own cadence — the drill tests *delivery*;
  effectuation is bounded by §4's contract, not by the drill).
  #609's acceptance sketch is the exit criterion verbatim: a specified
  box-side hook plus the controller-side publish path, with the
  propagation-latency bound stated *and tested*. No new daemons, no
  inbound ports, no control plane.
- **S1b — the rest of the box side:** the hook-loop timer unit (60–120s,
  local status write — the latency optimizer, not the enforcement
  point), the `toolset-update.sh` `_read_pin` cap, the G17 S2 mapping
  rows for the hook's log shapes (`skipped-frozen` / `deferred-arc`),
  and the fifth fleet alert rule (correlated gate-stale, read from the
  collector's answer-age field).
- **S2 — operator tooling:** `fleet freeze`/`unfreeze`/`promote`/`halt`
  writing through `gate_publish.py` (G15 §2's CLI), the hook's status
  file as a G16 collect artifact, key rotation UX (`key_id` dual-accept),
  multi-component registry UX. (The enforcement-point question is settled
  in S1a — the tick-time query enforces, the loop optimizes; S2 does not
  re-open it.)
- **S3 — hosted:** scheduler-facing per-tenant gate documents over the
  control-plane-internal path; no box-side hook on tenant boxes;
  box-identity attestation governs gate-*consumed events* (G13 §3 T2),
  not gate delivery; per-tenant waves (H11); no consent gate (G13 §1/T4).

## Open questions

1. **Hook-loop failure modes (settled in S1a; S2 hardening):** the
   tick-time query is the enforcement point, the 60–120s loop is the
   latency optimizer — if the loop dies, the tick still gates every
   deploy, and the local status file ages visibly. Optional S2
   belt-and-suspenders: the tick may additionally refuse when the
   status file is older than N× the hook interval, so a dead loop
   cannot silently become a dead gate.
2. **Cron fan-out for large estates**: at what fleet size does a
   sequential SSH fan-out break the stated freeze bound, and does S2
   need a fan-out relay (a per-site cache box) or a longer honest bound?
3. **Security-channel preemption**: a critical CVE needs the *current*
   wave to yield to the security channel's compressed waves — the
   document's single live wave per component cannot express "pause
   stable, run security". S2 schema or S3-only?
4. **`image` gating for operator estates**: operator boxes update
   in-place via auto-deploy (no reimage); the `image` field is
   tenant-fleet-only in S1. Does the operator estate ever need
   image-gating (golden-image operators)?

---
*Design for G18 (#609), from the 2026-09-28 fleet-rollout gap analysis
(`FLEET_UPDATE_ROLLOUT_GAP_ANALYSIS.md`). It delivers the transport half
of the G15/G18 split: G15's rollout-controller design
(`ROLLOUT_CONTROLLER_DESIGN.md` §5) states the box-side interface; this
doc specifies how the answer travels. Implementation (S1a–S1b/S2/S3)
remains — tracked on #609. Related: G15 (#606), G16 (#607, S1 shipped in `fleet/`),
G17 (#608), G11/G12 (`UPDATE_CHANNEL_POLICY.md`), G13 (#555), G14
(#556), H11.*
