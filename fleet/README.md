# fleet/ — fleet version inventory (G16 / #607), S1

Answers "what % of the fleet is on build X?" and "which boxes missed the
last update window?" from one place — the observability prerequisite for
fleet rollouts (G15/#606) and the P7 status page's fleet view.

Design: `docs/FLEET_VERSION_INVENTORY_DESIGN.md`. This is **S1**: the
local, pull-from-existing-artifacts slice. The operator's estate already
has per-box signals (`scripts/self_update.py status --json`, the
auto-deploy audit log); the collector reads them from a directory per
box. No new box-side daemon, no new inbound port, no control plane.

## Layout

- `inventory.py` — the collector + store + CLI (`collect`, `inventory`,
  `drift`, `rebuild`). Stdlib only.
- `box_snapshot.py` — box-side emitter producing the per-box
  `snapshot.json` the collector reads. Stdlib only.
- `test_inventory.py` — hermetic suite (run with `python3 -m pytest fleet`).
- `gate_publish.py` — controller side of the G18 release-gating channel:
  registry + wave manifest + freeze flag → signed `gate.json`. Stdlib only.
- `gate_query.py` — box side of the G18 channel: verifies `gate.json`
  and answers the box's self-evaluated state (`state` / `permitted`).
  Stdlib only.
- `gate_sync.sh` — the operator sync loop (G18 §4): copies the published
  `gate.json` to every box's `/var/lib/sparkvm/gate/`. Run from the
  operator's cron at ≤ TTL/2.
- `test_gate.py` — hermetic suite for the gating channel, including the
  §4 freeze drill (run with `python3 -m pytest fleet/test_gate.py`).

## Release gating (G18 / #777, S1a)

Design: `docs/RELEASE_GATE_CHANNEL_DESIGN.md`. One fleet-wide signed
document, published by the controller and synced to every box, tells each
box the maximum permitted versions per component, the live rollout wave,
and an orthogonal fleet-wide freeze. The box self-evaluates its wave from
its `box_id` (assignment pins, else `hash_mod_4`) and the repo updater caps
its deploy range at the gate's maximum permitted commit — an unregistered
commit never deploys on a gated box. Fail-closed: a missing, tampered, or
expired document freezes the box loudly; a missed sync loop is a visible
incident, not a silent rollout. The MAC (HMAC-SHA256, controller key)
stops on-path tampering and misconfiguration — the cross-box forgery
barrier is delivery-path ownership: the only writer of a box's gate dir is
the operator's sync loop. Key rotation is a document field (`key_id`);
during a rotation window the box accepts current + next, logging which
verified.

S1a enforces the **repo updater only** (the `pending_range()` cap). The
toolset `_read_pin` cap, the hook-loop status writer, and the `fleet
status` gate-stale line land in S1b (design §8).

### Provisioning (operator runbook)

```bash
# 0a. Estate layout: one dir per box; ssh-target names the scp destination
#     host (defaults to the dir name). Hostnames only — ports and extra
#     flags go in SSH_OPTS.
mkdir -p ~/fleet-estate/box-07
echo box-07.example > ~/fleet-estate/box-07/ssh-target

# 0b. Controller key: >=32 bytes, mode 0600 (gate_publish refuses the rest)
mkdir -p ~/fleet-keys
umask 077
head -c 32 /dev/urandom | base64 > ~/fleet-keys/ctl-2026-09.key

# 0c. Per box (the G18 §5 install step): box identity, the controller key
#     (0600, root-owned — gate_query refuses anything looser), and the gate
#     dir the sync loop requires to exist before it writes.
ssh root@box-07.example 'mkdir -p /etc/sparkvm /var/lib/sparkvm/gate && echo box-07 > /etc/sparkvm/box-id'
scp ~/fleet-keys/ctl-2026-09.key root@box-07.example:/var/lib/sparkvm/gate/ctl.key
ssh root@box-07.example 'chmod 600 /var/lib/sparkvm/gate/ctl.key'

# 0d. On the box's auto-deploy systemd unit, set:
#       Environment=SPARKVM_BOX_ID=box-07
#       Environment=SPARKVM_GATE_KEYS=ctl-2026-09=/var/lib/sparkvm/gate/ctl.key
#     (systemctl --system edit sparkvm-auto-deploy, then daemon-reload and
#     restart the timer)

# 1. Publish (controller machine; registry/manifest shapes: fleet/gate_publish.py --help)
python3 fleet/gate_publish.py --registry registry.json --manifest waves.json \
    --key-id ctl-2026-09 --key-file ~/fleet-keys/ctl-2026-09.key --out gate.json

# 2. Distribute (operator cron, <=5 min for the 600s S1 TTL)
GATE=gate.json ESTATE=~/fleet-estate fleet/gate_sync.sh
# Point your cron alerting at gate_sync.sh's exit code: a failed sync is
# the fleet-freeze signal, and a missed loop freezes the fleet by design.

# 3. Box side (tick-time query — the enforcement point)
python3 fleet/gate_query.py state --box-id box-07        # key=value answer
python3 fleet/gate_query.py permitted repo               # exit 0/1/2
```

Boxes without provisioned gate keys are gate-unmanaged: the updater
proceeds uncapped (pre-G18 behavior) — silently when the box was never
enrolled, with a warning when a gate document is present but no keys are
(the half-enrolled case: the operator forgot the install step). Run
`./deploy/auto-deploy.sh init` from a checkout carrying
`fleet/gate_query.py` to install the query side.

### Key rotation & retirement

1. Generate the next key and provision it to every box *alongside* the
   current one:
   `SPARKVM_GATE_KEYS=ctl-2026-09=/path/old,ctl-2026-10=/path/new`.
2. Publish with `--key-id ctl-2026-10`.
3. Confirm the fleet reports the new key: `gate_query.py state` shows
   `key_id=ctl-2026-10` on every box.
4. **Retire the old key**: remove its `key_id=/path` entry from every
   box's `SPARKVM_GATE_KEYS`. Until you do, the old key still signs
   fleet-accepted documents — rotation without retirement is a permanent
   second signing key.

## Quick start (operator estate)

```bash
# 1. Gather per-box artifacts: <estate>/<box>/{status.json,audit-tail.jsonl,snapshot.json}
#    - status.json:       `python3 scripts/self_update.py status --json` run on the box
#    - audit-tail.jsonl:  tail of the box's auto-deploy audit log
#    - snapshot.json:     `python3 fleet/box_snapshot.py --checkout ~/spark-vm` run on the box

# 2. Collect into the store (one record per box, journal + snapshot)
python3 fleet/inventory.py collect --estate ~/fleet-estate --store ~/fleet-store

# 3. Read the fleet
python3 fleet/inventory.py inventory --store ~/fleet-store
python3 fleet/inventory.py inventory --store ~/fleet-store --box tower
python3 fleet/inventory.py drift --store ~/fleet-store --expected <commit>

# 4. Rebuild a lost/corrupt snapshot (the journal is the source of truth)
python3 fleet/inventory.py rebuild --store ~/fleet-store

# 5. Read the update-event journal (G17 S1 — needs audit-tail.jsonl per box)
python3 fleet/inventory.py events --store ~/fleet-store
python3 fleet/inventory.py events --store ~/fleet-store --box tower
python3 fleet/inventory.py events watch --store ~/fleet-store   # exit 1 on unacked alerts
python3 fleet/inventory.py events ack --store ~/fleet-store --alert-id <id>
python3 fleet/inventory.py events crosscheck --store ~/fleet-store   # exit 1 on claim/inventory violations (G17 S2)

# 6. Age the journals out (G17 S2 retention — run on a schedule)
python3 fleet/inventory.py events prune --store ~/fleet-store   # 30d compact / 90d drop + old acked alerts
python3 fleet/inventory.py prune --store ~/fleet-store          # inventory journal 90d drop + snapshot rebuild
```

## Update events (G17 / #608, S1)

`collect` also canonicalizes each box's `audit-tail.jsonl` into the
store's `events.jsonl` — the standard event shape from
`docs/UPDATE_EVENT_REPORTING.md` §2 (`fleet/events.py`, stdlib only).
No box-side change: the canonicalizer translates the fifteen
(event, result) audit shapes the updaters already emit (see the
translation table in `events.py`, verified against
`deploy/auto-deploy.sh`'s `audit()` calls), with:

- **Fail-closed reads** — unparseable lines and unknown shapes become a
  collector note on stderr, never events; a gap in the audit tail is
  missing evidence, never inferred `noop`.
- **Noise discipline** — check-`noop` events stay local (never journaled).
- **Deterministic ids** — UUIDv5 over `box_id|ts|event|result|from|to`
  (per-subcomponent suffix on the plural-`components` success fan-out),
  so re-collection is a dedup no-op.
- **Alert rules, evaluated on every collect** — (1) `rollback-failed`
  within the evaluation scan window pages immediately (evaluation
  reasons only about the tail the armed rules can act on — the longest
  armed rule window, six hours; the journal file itself is still read
  in full, a later slice bounds the read; a `rollback-failed` older
  than the window that never fired no longer pages); (2) ≥2 boxes
  `failed`/`rolled-back` on the same (subcomponent, `to`) within
  30 min (the bad-release shape; lines with no component correlate on
  `to` alone as `unknown`) — both members must sit inside the scan
  window, so a cluster straddling the window edge is not detectable;
  (3) silent wave —
  **disarmed at S1** (every rollout envelope is null; firing it would
  page every healthy idle estate); (4) ≥3 `precheck-fail` on one box in
  6h. Alerts land in the store's `alerts.jsonl` (deduped on `alert_id`);
  `fleet events watch` exits 1 while any alert is unacknowledged — a
  cron or the operator's existing paging consumes it.
- **Known S1 limits** — session_epoch/rollout/window are null (no
  provisioner record, no G15 waves, no G14 windows); `attested` is always
  false.

## Journal retention (G17 S2)

Both journals age out on their own — run `prune` on a schedule (a daily
cron is plenty; prune is idempotent, and a no-op prune changes no
bytes):

```bash
python3 fleet/inventory.py events prune --store ~/fleet-store  # event journal + alerts
python3 fleet/inventory.py prune --store ~/fleet-store         # inventory journal
```

- **Event journal:** rows older than 30 days are compacted into
  per-day outcome histograms keyed (box, component, build) in
  `events_histograms.jsonl`; rows older than 90 days are dropped.
  Age is measured on `emitted_at` (when the event happened, never the
  collector's `received_at`); rows with a missing/unparseable
  `emitted_at` — and rows dated in the future — are always kept.
  Malformed lines survive verbatim. The raw journal's readers (list,
  watch, crosscheck) never see histogram rows.
- **Alerts:** only acknowledged alerts older than 90 days are dropped.
  Unacknowledged alerts are never pruned — a prune that silently
  deletes pending pages would be a lie.
- **Inventory journal:** rows older than 90 days (by `observed_at`) are
  dropped and the snapshot is rebuilt from the pruned journal, so a
  box whose only records expired disappears from the snapshot honestly
  (expired evidence is not evidence). Undatable/future rows are kept.

Both prunes hold the store's journal lock and rewrite journals
atomically (tmp + fsync + rename), so an overlapping collect's
appends are never lost to a prune's rewrite — and the collector's own
journal appends take the same lock for the same reason.

## Event<->inventory cross-check (G17 S2)

`fleet events crosscheck --store ~/fleet-store` checks each box's
`deploy`/`succeeded` claims against the inventory journal — the
fleet-side half of the design's claim-vs-ground-truth rule
(`docs/UPDATE_EVENT_REPORTING.md` §2). For each claim it finds inventory
records for the same box observed at-or-after the claim (collector clocks
on both sides; box clocks are never trusted for ordering):

- any later record showing the claimed commit → **confirmed**;
- later records exist but none shows it → **violation** (flagged, not
  convicted: the inventory wins the tie, the event keeps its journal
  row, nothing is marked suspect automatically);
- no later record, or later records report no commit → **inconclusive**
  (missing evidence is never a violation).

The command exits 1 while any violation is open (cron-consumable, like
`events watch`), 0 when clean or inconclusive-only. Only
`deploy`/`succeeded`/`repo` claims are checkable in this slice — the
design defines only `succeeded` as a claim (rolled-back/restored claims
are a follow-up), and the toolset/image components have no producers
yet.

The box dir name is the `box_id`; an operator-maintained remap file can
rename aliases: `collect --box-id-map box-ids.json` where the file is
`{"ssh-alias": "box-id"}`. `box_id` stability across reimage comes from
the mapping (operator keeps the alias on the box) until the
provisioner's per-box record (G15 §8) supersedes it.

## S1 semantics

- **Eligibility = freshness.** The census denominator is boxes whose
  latest record is fresher than `--staleness-hours` (default 24). Stale
  boxes are printed alongside the percentage, not hidden in it.
- **Cross-check.** The suspect flag compares the box snapshot against
  the audit tail's newest *successful* deploy/rollback claim: a failed
  deploy's `to` is an attempt, not a state claim (flagging it would mark
  honest boxes suspect), and `check` events carry no `to` so they can
  never shadow a deploy claim. On disagreement the box is marked
  `suspect` and the snapshot wins (point-in-time read beats a history
  of claims). Flagged, not convicted — `drift` shows the provenance.
- **Timestamps.** `observed_at` is collector-side; box-side
  `generated_at` is kept but never trusted for ordering. A
  `generated_at` more than 5 min in the future is flagged in the
  record's notes, not dropped. Both ISO-8601 strings and epoch
  numbers are accepted (the real `self_update.py` emits epoch ints).
- **`image_version: null` means "not applicable"** (in-place updater),
  never "unknown".
- **Drift's majority fallback has an inversion hazard.** Without
  `--expected`, drift compares against the fleet-majority commit — in
  the bad-build scenario the majority sits *on* the bad build and drift
  flags the good (rolled-back) boxes. Pass `--expected` explicitly
  whenever the expectation is known; the fallback is labeled honestly
  ("fleet majority", or "tie for majority" when there is none).
- **The journal is the per-rollout census series.** Only the live table
  is kept as a snapshot; reconstructing "the canary was 100% on the
  build for 3 hours" is a journal query. Journal growth: each collect
  appends one record per box carrying the full toolset payload — at the
  design's 10-minute cadence that is ~144 records/box/day; a
  retention/compaction policy: see UPDATE_EVENT_REPORTING.md §4 S2 (G17) —
  the 90-day/30-day journal discipline covers the inventory journal too.

## What's still S2/S3 (#607 stays open)

Push endpoint with box-identity auth, G15 gate integration (wave-k-did-it-land,
soak evidence, suspect exclusion), G13 attestation
(`attested: true` admission to the gate quorum), H11 per-tenant slicing,
P7 status-page projection.
