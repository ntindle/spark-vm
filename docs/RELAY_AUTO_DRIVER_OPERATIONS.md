# Relay auto-driver — operator's guide (S3 packaging, #1723)

The self-hosted scheduled path for the relay-liveness auto driver
(#1711). The timer invokes the S1 module (`hosted/relay_auto_driver.py`,
`tick_all_tenants`) once per sweep on the probe cadence.

**Enablement gate: do NOT enable the timer until #1724 (S4 — staleness
alert on the driver watermark) lands.** D-AC-6 pins the sequencing: a
scheduled driver with no staleness detector re-creates the #1711 death
mode the detector exists to kill. This slice ships the unit files and
this doc; the driver is inert packaging until the detector exists, at
which point the operator enables the timer per §1 below.

## 1. Install

The units ship in `hosted/` next to the module they drive:

- `hosted/relay-auto-driver.service` — the oneshot sweep
- `hosted/relay-auto-driver.timer` — fires the sweep on the probe cadence

Install (as the box owner, from the checkout root):

```bash
sudo sed -e "s|<CHECKOUT>|$PWD|" \
         -e "s|<BOX_OWNER>|ntindle|" \
         -e "s|<TENANT_STORE>|/home/ntindle/tenant-status/tenants.json|" \
         -e "s|<ESTATE_STORE_DIR>|/home/ntindle/.sparkvm-fleet|" \
         hosted/relay-auto-driver.service | sudo tee /etc/systemd/system/relay-auto-driver.service
sudo cp hosted/relay-auto-driver.timer /etc/systemd/system/relay-auto-driver.timer
sudo systemctl daemon-reload
# After the #1724 staleness alert lands:
# sudo systemctl enable --now relay-auto-driver.timer
```

The checkout itself must be operator-owned (a non-owner-writable
checkout is the same class of trust as a non-owner-writable
`<BOX_OWNER>` home — the unit's trust model in §6 assumes it).

`<TENANT_STORE>` is the same tenant-record JSON store path the
wiring's `--tick` CLI takes. `<ESTATE_STORE_DIR>` is the fleet estate
store dir whose `events.jsonl` receives the tick-note journal events
(D-AC-4) — omit `--journal-store-dir` (edit the unit's ExecStart) to
skip the journal leg; the watermark leg always runs.

To run one sweep by hand (what the timer fires — also the #1723
acceptance):

```bash
python3 -m hosted.relay_auto_driver_sweep \
  --store /home/ntindle/tenant-status/tenants.json \
  --journal-store-dir /home/ntindle/.sparkvm-fleet
```

## 2. The cadence knob

**D-AC-1 — one clock:** the drive cadence IS the probe cadence.
`hosted/relay_path_state.cadence_s()` reads `RELAY_PROBE_CADENCE_S`
(default `DEFAULT_CADENCE_S = 300.0`); the timer's `OnUnitActiveSec=5min`
matches the default by construction — `test_relay_auto_driver_packaging.py`
pins the equality, so a default change that forgets the timer file fails CI.

If the operator overrides `RELAY_PROBE_CADENCE_S` (systemd `Environment=`
on the service, or the environment), the two diverge:

- knob **above** the timer period: sweeps run more often than the
  cadence; a tick that finds no new reading is state-idempotent (the
  arc takes only the boolean flip, no transition) but NOT
  unobservable: every sweep still lands a watermark record and a
  fleet-journal tick-note per tenant and rewrites the store file.
  Safe, just extra work — journal/watermark/store churn per firing.
- knob **below** the timer period: the driver cannot drive faster than
  the timer; cadence granularity is lost. Keep the timer period ≤ the
  knob, or change both together.

## 3. Where the output goes

D-AC-4 — observability is a watermark + journal, not stdout:

- **Per-tenant last-tick watermark:** `<TENANT_STORE>.relay-tick-watermarks.json`
  (F-AC-5: the local sidecar next to the tenant store on the
  self-hosted path). One record per tenant per sweep:
  `{tenant_id, tick_at, applied, events, notes}` (+ the F-AC-7
  skip/stale/failed accounting). **This is what S4's staleness rule
  reads.**
- **Fleet journal:** `<ESTATE_STORE_DIR>/events.jsonl` gets one
  tick-note event per tenant per sweep (the G17 consumer contract;
  notes are control-char scrubbed at construction).
- **stdout:** the sweep prints the raw tick report JSON (per-tenant
  records + `errors`). Its audience is the unit's journal
  (`journalctl -u relay-auto-driver.service`) — for the operator
  reading a firing, not for machines. The report is terminal-safe:
  `json.dumps` escapes control bytes, so a tenant-controlled note
  can never inject escape sequences through this path.

## 4. The scheduled sweep vs manual `--tick`

Per D-AC-6 the scheduled path and the manual path are different
commands with different jobs — never interchangeable:

- `relay_auto_driver_sweep` (this unit): the schedule. Ticks **every**
  tenant, writes the watermark sidecar (the staleness signal), notes
  the journal. **Never** `--tick` on a schedule: `--tick` writes no
  watermarks, so scheduled `--tick` runs would leave the F-AC-5
  sidecar empty and S4's staleness rule hosted-plane-only —
  contradicting the both-supported default.
- `--tick` (in `hosted/relay_tenant_wiring.py`): the per-tenant
  manual/override path. A human runs it for one tenant when the
  sweep's record says "failed" and they want a retry now, or to
  check a tenant's wiring without waiting for the next firing.

Overlap rule (D-AC-3): a manual `--tick` racing a scheduled sweep is
**safe, not prevented** — ticks are bounded and the apply phase is
idempotent under the store lock, so concurrent ticks converge. No
leader election, no flock around the schedule. "Anchor moved" skips
are convergence, not driving: they count separately and never read
as applied.

## 5. Failure posture

- One tenant's broken instrument never wedges the sweep: its tick
  fails loud in its own record (`failed: true`, notes carry the
  exception) and the driver moves on. The sweep still exits 0 — the
  failure is evidence, in the watermark.
- The sweep exits 2 (one line on stderr, unit shows failed) only
  when the sweep itself could not run: bad input, unreadable store,
  internal error.
- A wedged watermark sidecar never wedges the sweep: the tick still
  drives, the failure lands LOUD on the tenant's record (and in the
  report's `errors[]`), the sweep still exits 0 — the unit shows
  success. The MISSING fresh watermark is what S4's staleness rule
  reads as driver trouble (#1724): staleness reads the sidecar, not
  the unit state.

## 6. Trust note

The timer executes the checkout's code — the same trust as the
wiring's `--tick` CLI the schedule replaces. The auto-deploy
installed-copy discipline (#85) is deliberately not applied here:
this is a local oneshot CLI on the operator's own box, not a network
service, and the timer grants no privilege beyond the operator's
existing own. Revisit if the driver ever leaves the operator's box
(e.g. the S2 plane port, #1722, has its own async trust boundary).
