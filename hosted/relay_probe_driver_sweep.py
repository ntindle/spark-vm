#!/usr/bin/env python3
"""Relay probe-driver sweep entry point, S5 (issue #1837 / #1711 remainder).

The scheduled half of the probe loop's both-supported story: a
cron/systemd timer invokes THIS module once per sweep (see
``hosted/relay-probe-driver.{service,timer}`` +
``docs/RELAY_PROBE_DRIVER_OPERATIONS.md``). It drives
``probe_all_tenants`` — the S5 probe driver — never ``--probe-now``:
``--probe-now`` is the per-vm manual/override path (it takes one VM id
plus the bundle on stdin); only the sweep writes the per-tenant probe
watermarks and probe-note journal events the S1 auto-driver's
loud-stale note reads.

The bundle supplier is the deployer's seam (D-RL2-3): this module
supplies none, so a due tick with no bundle is noted LOUD (the
dark-instrument steady state), never failed. Provider state defaults
to ``running`` (mirrors the ``--probe-now`` CLI's
``--provider-state``); the post-``live`` answer is derived from the
real wiring store's anchor arc per tenant.

The report JSON goes to stdout — the unit's journal is its audience
(D-AC-4 observability is watermark + fleet journal, not stdout; stdout
is the raw report for the operator reading the timer's journal). The
report itself is terminal-safe: ``json.dumps`` escapes control bytes,
so a tenant-controlled note can never inject escape sequences into
the unit's journal through this path.

Exit contract: 0 when the sweep completed and the report printed
(per-tenant probe failures are IN the report per D-AC-3 — a broken
tenant instrument fails loud in its own record, never the sweep; a
wedged watermark sidecar lands as the single #1838 sweep-level
errors[] entry and still exits 0 — the S4 staleness rule reads the
sidecar's absence, not the unit state); exit 2 when the sweep
itself could not run (bad input / unreadable store / internal
error), one line on stderr, never a bare traceback.
"""

import argparse
import json
import os
import sys

# Same invocation shape as the sibling CLIs: run from the checkout root
# as ``python3 -m hosted.relay_probe_driver_sweep`` so ``hosted`` is a
# package on sys.path.
from hosted import relay_probe_driver as pdriver
from hosted import relay_tenant_wiring as wiring
from hosted import tenant_status as ts


def build_parser():
    ap = argparse.ArgumentParser(
        description="Probe every tenant's live anchor once (the scheduled "
                    "probe-driver path, #1837)."
    )
    ap.add_argument(
        "--store",
        required=True,
        help="tenant-record JSON store path (the same store the "
             "wiring's --tick CLI takes); the probe watermark sidecar "
             "lands next to it via probe_watermark_path_for()",
    )
    ap.add_argument(
        "--journal-store-dir",
        default=None,
        help="fleet estate store dir whose events.jsonl receives one "
             "probe-note event per tenant (D-AC-4); omit to skip the "
             "journal leg",
    )
    ap.add_argument(
        "--journal-timeout-s",
        type=float,
        default=None,
        help="journal-lock wait seconds for the producer read "
             "(mirrors the --tick CLI)",
    )
    ap.add_argument(
        "--history",
        default=None,
        help="probe-history path override (mirrors the --tick CLI; "
             "else RELAY_PROBE_HISTORY / the module default)",
    )
    ap.add_argument(
        "--journal",
        default=None,
        help="session-journal path override (mirrors the --tick CLI; "
             "else RELAY_SESSION_JOURNAL / the module default)",
    )
    ap.add_argument(
        "--provider-state",
        default="running",
        help="H4 provider state string fed to every tenant's probe "
             "(mirrors the --probe-now CLI; default: running)",
    )
    return ap


def _make_post_live_fn(store):
    """Derive the post-``live`` answer from the real wiring store.

    The probe driver's ``post_live_fn(tenant_id, vm_id)`` is the tenant
    layer's answer; the scheduled path reads it off the tenant's
    anchor arc — the same arc the probe tick itself selects
    (``select_live_anchor`` is deterministic, so the answer is
    consistent with the probed anchor).
    """
    def _post_live(tenant_id, vm_id):
        rec = store.get(tenant_id)
        if rec is None:
            # Benign race (the module's own wording): the tenant was
            # deleted mid-sweep — the probe tick notes it; the answer
            # here only feeds the stand-down label.
            return False
        anchor = wiring.select_live_anchor(list(rec.boxes.values()))
        return anchor is not None and wiring.has_post_live_arc(anchor)

    return _post_live


def main(argv=None):
    args = build_parser().parse_args(argv)
    store_path = os.path.abspath(args.store)
    if args.history:
        os.environ["RELAY_PROBE_HISTORY"] = args.history
    if args.journal:
        os.environ["RELAY_SESSION_JOURNAL"] = args.journal
    try:
        store = wiring.TenantFileWiringStore(ts.TenantStore(store_path))
        report = pdriver.probe_all_tenants(
            store,
            watermark_path=pdriver.probe_watermark_path_for(store_path),
            journal_store_dir=args.journal_store_dir,
            provider_state_fn=lambda tid, vm: args.provider_state,
            post_live_fn=_make_post_live_fn(store),
            bundle_fn=None,  # D-RL2-3: the deployer's seam; dark-instrument default
            history=args.history,
            journal_timeout_s=args.journal_timeout_s,
        )
    except Exception as exc:  # noqa: BLE001 - operator contract: one-line error, exit 2
        print("relay_probe_driver_sweep: error: %s" % exc, file=sys.stderr)
        return 2
    # json.dumps (not print-of-str) keeps tenant-controlled notes
    # terminal-safe in the unit's journal.
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
