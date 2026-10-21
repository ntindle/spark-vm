# Relay probe driver — operator's guide (S5 packaging, #1837)

The self-hosted scheduled path for the relay-liveness probe loop
(#1711). The timer invokes the S5 probe driver
(`hosted/relay_probe_driver.py`, `probe_all_tenants`) once per sweep
on the probe cadence, feeding the probe history the S1 auto-driver's
loud-stale note reads.

**Enablement gate: do NOT enable the timer until #1724 (S4 — staleness
alert on the driver watermark) lands.** D-AC-6 pins the sequencing: a
scheduled probe loop with no staleness detector re-creates the #1711
death mode for the probe lane — a dead probe loop would silently
revert S1 to loud-stale ticks with nobody noticing. This slice ships
the unit files and this doc; the loop is inert packaging until the
detector exists, at which point the operator enables the timer per §1
below. (The S1 loud-stale note is the probe loop's interim death
signal: it tells "probe loop dead" from "driver dead".)

## 1. Install

The units ship in `hosted/` next to the module they drive:

- `hosted/relay-probe-driver.service` — the oneshot sweep
- `hosted/relay-probe-driver.timer` — fires the sweep on the probe cadence

Install (as the box owner, from the checkout root):

```bash
sudo sed -e "s|<CHECKOUT>|$PWD|" \
         -e "s|<BOX_OWNER>|ntindle|" \
         -e "s|<TENANT_STORE>|/home/ntindle/tenant-status/tenants.json|" \
         -e "s|<ESTATE_STORE_DIR>|/home/ntindle/.sparkvm-fleet|" \
         hosted/relay-probe-driver.service | sudo tee /etc/systemd/system/relay-probe-driver.service
sudo cp hosted/relay-probe-driver.timer /etc/systemd/system/relay-probe-driver.timer
sudo systemctl daemon-reload
# After the #1724 staleness alert lands:
# sudo systemctl enable --now relay-probe-driver.timer
```

The checkout itself must be operator-owned (a non-owner-writable
checkout is the same class of trust as a non-owner-writable
`<BOX_OWNER>` home — the unit's trust model in §6 assumes it).

`<TENANT_STORE>` is the same tenant-record JSON store path the
wiring's `--tick` CLI takes. `<ESTATE_STORE_DIR>` is the fleet estate
store dir whose `events.jsonl` receives the probe-note journal events
(D-AC-4) — omit `--journal-store-dir` (edit the unit's ExecStart) to
skip the journal leg; the watermark leg always runs.

To run one sweep by hand (what the timer fires — also the #1837
acceptance):

```bash
python3 -m hosted.relay_probe_driver_sweep \
  --store /home/ntindle/tenant-status/tenants.json \
  --journal-store-dir /home/ntindle/.sparkvm-fleet
```

## 2. The cadence knob

**D-AC-1 — one clock:** the probe cadence IS the drive cadence.
`hosted/relay_path_state.cadence_s()` reads `RELAY_PROBE_CADENCE_S`
(default `DEFAULT_CADENCE_S = 300.0`); the timer's `OnUnitActiveSec=5min`
matches the default by construction —
`test_relay_probe_driver_packaging.py` pins the equality, so a default
change that forgets the timer file fails CI.

## 3. Output audience

The sweep prints the probe-tick report JSON to stdout — the unit's
journal is its audience (D-AC-4: the probe watermark + fleet journal
are the durable observability). The report is terminal-safe
(`json.dumps` escapes control bytes). The operator reads:

- the per-tenant probe watermark sidecar (`<TENANT_STORE>.relay-probe-watermarks.json`)
  — one last-probe-tick record per tenant; a dead probe loop shows as
  missing/stale records here, distinct from the drive watermark (S4's
  fail-visible story);
- the fleet journal's probe-note events (`events.jsonl` in the estate
  store dir).

## 4. Sweep-vs-manual

<a id="sweep-vs-manual"></a>

The scheduled sweep drives `probe_all_tenants` — the S5 module — never
`--probe-now`. `--probe-now` is the per-vm manual/override path (one VM
id, the bundle on stdin); driving it on a schedule would leave the
F-AC-5 probe watermark sidecar empty and the S1 loud-stale note would
read the manual probes' history, contradicting the both-supported
default. `--probe-now` stays the manual path; it is never the scheduled
path.

## 5. Failure posture

- A broken tenant instrument fails loud in its own probe record
  (`failed=True`) and never wedges the sweep (D-AC-3).
- A wedged probe-watermark sidecar (ELOOP plant on the read leg, #1838;
  ELOOP plant on the bulk-write lock, disk-full, permission — #1842)
  lands as the single sweep-level `errors[]` entry and still exits 0 —
  the S4 staleness rule reads the sidecar's absence, not the unit state.
- The sweep itself failing (bad input, unreadable store) exits 2 with
  one line on stderr, never a bare traceback.
- No bundle wired (D-RL2-3): a due tick is noted LOUD
  (dark-instrument), never failed. The bundle supplier is the
  deployer's seam — this unit never invents one.
- Pathology budget (#1836, mirrored from the S3 unit): the unit kills
  a sweep that runs past `TimeoutStartSec=240s` — a wedged sweep's only
  signal until #1724 lands is `journalctl -u relay-probe-driver.service`;
  after #1724, the missing fresh probe watermark is the fail-visible
  signal. The journal READ lock wait is tick-scale
  (`--journal-timeout-s 30`); the journal APPEND leg is still the 300s
  fleet default until #1746 lands.

## 6. Trust note

Same trust model as the auto-driver sweep: the timer executes the
checkout's code on the operator's own box; it grants no privilege
beyond the operator's existing own. Provider state defaults to
`running` (`--provider-state`, mirroring the `--probe-now` CLI); the
flag is NOT inert (the sweep ships with no bundle, D-RL2-3, but
`maybe_probe` still reads provider state on every tick before the
bundle check) — a tenant whose provider reads `suspended`/`destroyed`
stands down observably (`stand_down=True`) even with no bundle wired,
and a stand-down record carries no dark-instrument note. With no
bundle the dial itself never runs; wire a bundle supplier for probes
to actually dial. The post-`live` answer is
derived from the real wiring store's anchor arc.
