# Fleet version inventory — design (G16 / #607)

The per-box updaters report plenty: `self_update.py status --json` is a
machine-readable toolset inventory (S1 of #532), and `deploy/auto-deploy.sh`
appends every run to a per-box audit log. But nothing *collects* either.
The operator cannot answer "what % of the fleet is on build X?" or "which
boxes missed the last update window?" from one place — and without that
answer, G15's rollout waves cannot be observed and a bad release cannot be
scoped ("how many boxes got the bad build before the halt?").

This doc designs the fleet version inventory: the collector and store that
aggregate per-box version reports into a fleet version table. It is the
design behind G16 (#607); it is what `ROLLOUT_CONTROLLER_DESIGN.md` §4's
gates read ("what each box is actually running") and §8's "reads, never
owns" line names, without re-litigating the controller itself. It consumes
G17 (update event reporting, #608) for cross-checking but does not design
the event pipeline; it waits on G18 (the fleet→box channel, #609) for
nothing — the S1 inventory is deliberately pull-from-existing-artifacts
first.

Scope note (both-supported default, per PLAYBOOK): the inventory is a repo
component any self-hosted operator with N boxes runs against their own
estate; the hosted product runs the same component as a control-plane
endpoint for tenant fleets. The per-box reporters are the same boxes the
per-box updaters already run on — no new box-side daemon beyond what §5
names.

## 1. The two questions the inventory must answer

Everything else in this design is detail. The inventory exists to answer:

1. **"What % of the fleet is on build X?"** — a per-release census, at any
   moment: for each component (repo commit, toolset pins, image version),
   the fraction of eligible boxes reporting that version.
2. **"Which boxes missed the last update window?"** — per-box liveness
   relative to expectation: which boxes should have converged by now (their
   wave moved, their tick ran) but report an older build or no report at
   all.

The second question is the harder one: it requires the inventory to know
what "should have" happened — which is why it reads the rollout
controller's wave manifests (box→wave assignment), the rollout record
(promotion timestamps, gate snapshots — this is where the wave's
promotion timestamp lives; the manifest and registry don't carry it),
and the release registry alongside the per-box reports (§6).

## 2. What the boxes already report (signal inventory)

Before adding anything, name what exists:

- **Toolset dimension — covered.** `scripts/self_update.py status --json`
  emits `{generated_at, slice, tools, pin_warnings}` where each tool
  record is `{tool, scope, installed, version, pinned, drift, note}` —
  stdlib only, exit 0 always (probe failure is a `note`, never a crash).
  Machine-readable since S1, and currently consumed by nobody. This is
  the toolset-pin dimension of the record, ready-made.
- **Deploy dimension — half covered.** `deploy/auto-deploy.sh` audits
  every run to a per-box audit log capped at 10k lines. The event is
  `deploy` (or `check`/`rollback`); the outcome lives in the `result`
  discriminator (`ok`, `rolled-back`, `rollback-failed`, `deploy-fail`,
  `precheck-fail`, `gate-fail`, `snapshot-fail`, `checkout-dirty`,
  `pull-only`, `reload-fail`, `manual-rollback`, …) alongside `from`/`to`
  commits, component, and phase. The log says *what happened*; it does
  not carry a standing "what am I running now" snapshot.
- **Missing entirely:** a per-box `box_id` that survives reimage (the G15
  doc's §8 requirement on the provisioner's per-box record — required
  here too, for the same reason: a reimaged tenant box is a new session
  internally, but the inventory row must follow the box, not the boot),
  a current-repo-commit snapshot distinct from the audit trail, the
  `image_version` for tenant boxes once G11's provisioner tracking lands
  (#553's box-side half), and the box-side gate-answer age (so the
  inventory can distinguish "frozen by policy" from "frozen by partition",
  per the G15 doc's §5 fail-closed semantics).

No new telemetry daemon is required in S1: the inventory reads existing
artifacts. The collector adds the missing box-side fields as cheap,
existing-artifact-derived snapshots (see §5).

## 3. Component shape

One repo component, `fleet/` (same component as the controller; the
inventory is the controller's read model):

- **Collector** — turns per-box signals into inventory records. S1: an
  operator-estate collector the operator runs from a cron or by hand,
  pulling from boxes over their existing SSH access (no new inbound port
  on the box); S2: a control-plane endpoint boxes push to (when the hosted
  plane exists); both write the same record schema (§4).
- **Store** — a JSONL journal + snapshot, same discipline as the repo's
  other components. Records are append-only observations with timestamps;
  the snapshot is derived and rebuildable. Same rule as the controller's
  journal: the fleet's version history is auditable after the fact —
  "when did box X leave build Y?" must be answerable retroactively.
- **CLI** — `fleet inventory` (the fleet version table: per-box versions,
  staleness flags, census percentages per release), `fleet inventory
  --box <id>` (one box's version history), `fleet drift` (raw
  disagreement between reported versions and the wave's permitted
  version — §6 defines the actionable "missed the window" subset).

State lives on the operator's machine (or the control plane), never on
the boxes — the inventory is a read of the fleet, not a resident of it.

## 4. The record schema

One record per (box, observation):

- `box_id` — stable box identity. The long-term home is the
  provisioner's per-box record (provisioned at install, MUST survive
  reimage — the G15 doc's §8 requirement on the provisioner, per G11).
  S1 cannot wait for that: the operator's existing boxes have no
  provisioner and no install flow. The S1 interim rule is an
  operator-maintained `box_id`→box mapping file (ships as a sample
  config) read by the collector, defaulting to the SSH host alias the
  operator already uses; reimage-stability comes from the mapping (the
  operator keeps the alias on the box), not from a provisioner. The
  provisioner path stays the S2/S3 target, and the record schema is
  identical either way.
  S1 ships the sample as a CLI flag: `fleet/inventory.py collect
  --box-id-map box-ids.json` where the file is a JSON object mapping
  estate directory names (SSH host aliases) to box_ids.
- `observed_at` — collector-side timestamp. Box-side `generated_at` is
  kept in the payload but never trusted for ordering (clock skew, §11).
- `reporter` — what produced this record: `auto-deploy-audit`,
  `self-update-status`, `gate-hook-snapshot`, or `control-plane-probe`
  (§5). Records keep their provenance so the collector can weight them.
  S1 deviation (2026-09-29): the shipped pull collector stamps
  `estate-collector-s1`, which predates this enum — the enum gains the
  S1 value (or the collector adopts one) before any strict consumer
  validates it.
- `versions` — the three dimensions:
  - `repo_commit`: current deployed commit of the box's spark-vm checkout
    (from auto-deploy's snapshot, not from a fresh `git rev-parse` at
    collect time — the deployed-commit discipline from the update design).
  - `toolset_pins`: the `self_update.py status --json` payload, as-is
    (collector does not re-interpret pin warnings; it carries them).
  - `image_version`: for tenant boxes, the provisioner-tracked image
    version once G11's tracking lands; operator boxes report `null`
    (in-place updater, no image dimension) — `null` means "not
    applicable", never "unknown".
- `last_tick_at` — per-dimension timestamp of the last box-side
  updater run the collector saw (auto-deploy tick from the newest
  `deploy` audit `ts`; toolset tick from the `status --json`
  `generated_at`; reimage from the newest `image_version` change). This
  is the datum §6's "missed the window" definition needs ("whose last
  update tick ran after the wave's promotion timestamp") and §6's
  post-incident scoping needs — it is stored in the record, not
  recomputed, because the audit tail the collector read from may have
  rolled on by the time someone asks retroactively.
- `gate` — the box-side hook's last known gate state: permitted commit,
  permitted toolset pin (the G15 doc's §5 second enforcement point —
  the gate answer carries both), frozen flag, and answer age. This is
  what lets the inventory distinguish "held by policy" from
  "partitioned": a box reporting an old build *and* `frozen: true` is
  obeying; a box reporting an old build with a stale gate answer is
  degraded.
- `suspect` — derived state, not a box report: true when the box has
  persistent report-vs-audit inconsistencies (§7). Computed by the
  collector from the inconsistency journal and carried on the record
  (and snapshot) so gate consumers get it without recomputing; a
  `suspect` box is G16's proposed interface contract to the G15 gates
  (S2): exclude it from the promotion quorum (it cannot *pass* a wave),
  and never let one suspect box *halt* a wave on its own. The G15 doc
  only says gates evaluate eligible boxes "with a minimum quorum" —
  this contract is G16's proposal for how suspect feeds that quorum,
  not an existing G15 decision.
- `wave` — the box's current wave assignment (copied from the wave
  manifest at collect time; a copy, not a join — the manifest may move on).
- `arc` — whether the box had an active tenant arc at collect time
  (never-interrupt-an-arc means "old build + active arc" is *deferred*,
  not missed — §6).
- `attested` — false in S1 (self-reported, unweighted — §7); true only
  when G13 attestation backs the report (tenant-fleet instantiation).

## 5. Collection paths: pull first, push when the plane exists

**S1 — the operator pulls (ships first).** The operator's estate already
has SSH to its boxes. The S1 collector runs on the operator's machine
(from a cron or by hand), connects to each known box, and reads three
artifacts:
> **S1 implementation note (2026-09-29):** the shipped S1 collector
> (`fleet/inventory.py collect`) reads from a local estate directory —
> one subdirectory per box holding the three artifacts, which the
> operator rsyncs/scps together (or points at a mounted tree) — rather
> than pulling over SSH itself. The record schema and the store are
> unchanged either way; live SSH pull is a later collector slice.
the tail of the auto-deploy audit log, a fresh
`self_update.py status --json` run, and a small box-side snapshot script
that emits `{repo_commit, gate_answer_age, frozen, arc_active,
image_version}` — all derived from on-box state the updaters already
maintain, nothing new invented for the inventory. Collection cadence: no
faster than the auto-deploy tick (10 min); faster collection buys nothing
the box hasn't yet converged to.

S1 is pull because the operator estate has no control plane and no box
should open a new inbound listener for inventory. It is also the
trust-appropriate choice: the operator already trusts these boxes
(G15 doc §6 — the operator estate starts without event attestation).

**S2 — boxes push to the control plane.** When the hosted plane exists
(and for operator estates that want it), the G18 channel carries
inventory reports *out* as well as gate answers *in*: the box-side hook
that polls the gate every 60–120s (G15 doc §5) appends its snapshot to
its push. Push reports carry the same schema; the endpoint authenticates
the box (its provisioned identity) and stamps `observed_at` server-side.
Push does not replace pull for the operator estate — it is the second
instantiation of the same record stream.

**S3 — hosted tenant-fleet.** Same as S2, plus the two tenant-fleet
constraints from the G15 doc's §6: inventory reports that G15 gates
consume require G13 attestation (`attested: true`), and per-tenant wave
scoping (H11) means the fleet version table is sliced per tenant — one
tenant's census never leaks another tenant's box list.

What S2/S3 add that S1 cannot: freshness below 10 minutes and boxes the
operator cannot SSH to (tenant boxes). What S1 keeps forever: the
zero-new-infrastructure path — the inventory must never *require* the
control plane, because the open-source operator has no control plane.

## 6. The semantics: "missed the window", drift, and the % census

The two questions from §1 need definitions, or the CLI output is
arguable:

- **Eligible boxes** — the same set the G15 gates evaluate: reachable ∧
  not arc-deferred ∧ not suspended. A box asleep through its wave does
  not "miss" anything (G14's decision, still open — the inventory
  implements whatever G14 says about wake semantics, it does not decide
  it). The census denominator is eligible boxes, and `fleet inventory`
  prints the denominator and the excluded counts alongside the
  percentage — a 100% census over 2 eligible boxes out of 50 is honest
  only if the 48 exclusions are visible.
- **Missed the window** — an eligible box whose reported `repo_commit`
  (or toolset pin, or image_version) is older than the version its wave
  was permitted *and* whose last update tick ran after the wave's
  promotion timestamp. "Older than permitted" alone is not missed — a
  box mid-tick is converging. "Tick ran after promotion, still old" is
  missed: the box had its chance and didn't take it. The G17 event
  stream (once it exists) sharpens this: a failed/rolled-back event
  explains the miss; no event at all means the box is sick, not merely
  slow.
- **Drift** — `fleet drift` lists boxes whose versions disagree with
  their wave's permitted version *for any reason*, including policy
  holds (frozen) and arc deferrals. Drift is the raw list; "missed the
  window" is the actionable subset. Both are needed: drift answers
  "what does the fleet actually look like?", missed-the-window answers
  "what needs attention?".
- **Per (box, build) evidence** — the G15 gates consume soak evidence
  keyed on (box, build), and the inventory is where that evidence lives:
  the store's journal is a per-box version timeline, so "box X has been
  on build Y since T" is a range query, not an inference. Reimage resets
  the box's timeline position (G11: new session internally) but keeps
  the row — the box's *history* survives the reimage even though its
  soak evidence for the new build starts at zero.
- **Baseline comparison** — the G15 doc's §4 baseline (per-wave failure
  rates) needs per-wave, per-build population counts over time; the
  inventory's census snapshots are that series. The inventory keeps
  census snapshots per rollout, not just the live table — "the canary
  was 100% on the build for 3 hours" must be reconstructable after the
  rollout completes.

## 7. Trust: observed, not attested (until G13)

The operator-estate inventory is **self-reported signal, explicitly
unweighted**. A box that lies about its version can make the census
lie — and the design says so plainly rather than pretending otherwise.
Three compensating mechanisms, all cheap:

1. **Cross-check with G17 events** (once they exist): an update event
   says "box X deployed commit C at T"; the next inventory record from
   box X should say it's on C. A mismatch (event says deployed, box
   says old) is a flagged inconsistency, not silently absorbed —
   `fleet drift` shows it with its provenance. Until G17 exists, the
   cross-check is against the auto-deploy audit tail the collector
   already pulls: the audit's own `from`/`to` claims are compared
   against the snapshot, same flag on mismatch. On disagreement, the
   snapshot emitter is authoritative for `versions.repo_commit` — it
   is a point-in-time read of deployed state, while the audit tail is
   a history of claims about what *should* have been deployed.
2. **Report-shape anomalies**: a box whose `status --json` suddenly
   stops carrying pin warnings it always carried, or whose audit tail
   skips sequence, is flagged — not convicted, flagged. The inventory
   detects *change*, it does not adjudicate *malice*.
3. **Quarantine, not exclusion**: a box with persistent inconsistencies
   is marked `suspect` (§4, derived state) in the table. The proposed
   S2 interface contract to the G15 gates: suspect boxes are
   excluded-from-quorum (they cannot *pass* a wave), but one suspect
   box cannot *halt* a wave either — a tenant cannot halt a good
   release by lying, per the G15 doc's §6 event-authenticity constraint.

For the tenant-fleet instantiation, S3 requires G13 attestation on the
reports the gates consume: `attested: true` is the admission ticket to
the gate quorum. Unattested reports still land in the inventory (the
operator's table can show them) but are excluded from promotion
decisions. The operator estate never needs this — trusted boxes, one
operator — but the schema carries the flag from S1 so the hosted path
doesn't redesign the record.

## 8. What the inventory feeds

- **G15 gates** (the primary consumer): wave-k-did-it-land checks, soak
  evidence per (box, build), the baseline population series, suspect-box
  exclusion. The controller reads the inventory; it never writes to it —
  the inventory is the fleet's memory, the controller is the fleet's
  will.
- **The P7 status page** (read-only ops archetype): fleet health needs
  fleet versions — the status page's fleet view is a projection of the
  census, not a second source of truth.
- **Post-incident scoping**: "how many boxes got the bad build before
  the halt?" is a journal query bounded by the halt timestamp. This is
  the question the inventory exists for after a bad release — and it is
  why the store is append-only: the answer must survive the remediation
  (boxes that already rolled back must still be countable as having
  *been* on the bad build).
- **The operator's own runbooks**: `fleet drift` before a maintenance
  window, `fleet inventory --box` when a box behaves oddly.

What it does *not* feed: nothing in the inventory *commands* a box.
Reports flow in; gate answers (G18) and rollout decisions (G15) flow out
through their own channels. An inventory that could command is a
controller, and this design already has one.

## 9. Deliberately out of scope

- **The G17 event pipeline** (#608): the inventory cross-checks against
  events; it does not design event transport, ordering, or retention.
- **G18's transport** (#609): S1 is pull-over-SSH by design; S2/S3 push
  over whatever G18 delivers. The inventory states its payload (§4) and
  its freshness needs (§5); G18 picks the wire.
- **What an update is** (G11–G14): decided elsewhere; the inventory
  records versions, it does not bless transitions.
- **Box identity provisioning**: required (survives reimage), designed
  with the G15 doc's §8 — this doc consumes the requirement, it does
  not re-specify the provisioner.
- **Per-box health beyond versions**: CPU, disk, arc state beyond the
  active/inactive bit — the status page's problem, not the inventory's.
  The inventory answers version questions; health questions need their
  own design.

## Build slices

- **S1 — local inventory (ship first):** `fleet/` inventory skeleton:
  the record schema (§4) as a JSONL journal + snapshot store, the S1
  pull collector (SSH over the operator's existing access; reads the
  three artifacts in §5), the box-side snapshot emitter (derived from
  existing updater state — no new daemon), `fleet inventory` / `fleet
  inventory --box` / `fleet drift` CLI, census snapshots per rollout,
  suspect-flagging from audit/snapshot cross-checks. Operator manual
  reading only — no gate integration yet.
- **S2 — gates + control plane:** push endpoint (§5) with
  box-identity authentication and server-side `observed_at`; G15 gate
  integration (wave-k-did-it-land, soak evidence, baseline series,
  suspect exclusion); G17 cross-checks; operator-defined drift
  predicates alongside the canned ones.
- **S3 — hosted + attestation:** tenant-fleet instantiation behind G13
  attestation (`attested` admission to the gate quorum) + H11
  per-tenant slicing; G14 wake semantics honored for the eligibility
  set; P7 status-page fleet projection.

## Open questions

1. **Snapshot emitter placement**: is the box-side snapshot a script the
   collector invokes over SSH (S1), or a file the updaters refresh on
   every tick (S2 push reads it)? The file is fresher for push; the
   script is one less writer for pull. S1 says script; S2 may want the
   file — decide at S2 build time, keep the schema (§4) stable across
   both.
2. **Retention**: census snapshots per rollout are kept how long? The
   journal is append-only "forever" in S1, which is fine at operator
   scale and wrong at tenant-fleet scale. Name the retention policy in
   S3; S1 keeps everything and says so.
3. **box_id format**: the G15 doc requires stability across reimage but
   doesn't name the format, and §4 names the S1 interim rule
   (operator-maintained mapping, SSH host alias default) with the
   provisioner path as the S2/S3 target. Decide the long-term format
   with the provisioner work (UUIDv4 in the provisioner record, or
   derived from the box's Tailscale identity?), not here — the record
   schema carries `box_id` either way.
4. **Clock skew**: `observed_at` is collector-side (S1) / server-side
   (S2) precisely so skew doesn't poison ordering — but the box-side
   `generated_at` still matters for "how stale is this report".
   Skew bound: reject reports whose `generated_at` is in the future
   beyond a tolerance (5 min), flag don't drop.
5. **Missed-window alerting**: `fleet drift` is a CLI; who pages the
   operator when the missed list grows? P7's status page is the read
   surface; whether the inventory itself alerts is an S2 question, and
   the answer is probably "the status page alerts, the inventory
   supplies the query".

---
*Design for G16 (#607), from the 2026-09-28 fleet-rollout gap analysis
(`FLEET_UPDATE_ROLLOUT_GAP_ANALYSIS.md`). Complements the rollout
controller design (`ROLLOUT_CONTROLLER_DESIGN.md`, G15/#606): the
controller reads this inventory for its gates (§4) and this inventory
reads the controller's wave manifests for its "missed the window"
semantics (§6). S1 shipped 2026-09-29 as the fleet/ component (JSONL journal + rebuildable snapshot, estate-dir pull collector, box-side snapshot emitter, inventory/drift/rebuild CLI, hermetic suite); S2–S3 remain — tracked on #607.
Related: G17 (#608), G18 (#609), G15 (#606), G13 (#555), G11–G12
(UPDATE_CHANNEL_POLICY.md), P7 (status page).*
