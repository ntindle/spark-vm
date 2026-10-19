#!/usr/bin/env python3
"""Relay auto-driver sweep entry point, S3 (issue #1723 / #1711 remainder).

The scheduled half of the both-supported driver story: a cron/systemd
timer invokes THIS module once per sweep (see
``hosted/relay-auto-driver.{service,timer}`` + ``docs/RELAY_AUTO_DRIVER_OPERATIONS.md``).

D-AC-6 (``docs/RELAY_LIVENESS_AUTO_CADENCE_GAP_ANALYSIS.md``): the
scheduled path drives ``tick_all_tenants`` — the S1 module — never
``--tick``. ``--tick`` writes no watermarks, so driving it on a
schedule would leave the F-AC-5 sidecar empty and S4's staleness rule
hosted-plane-only, contradicting the both-supported default. ``--tick``
stays the per-tenant manual/override path (D-AC-2); it is never the
scheduled path.

The report JSON goes to stdout — the unit's journal is its audience
(D-AC-4 observability is watermark + fleet journal, not stdout; stdout
is the raw report for the operator reading the timer's journal). The
report itself is terminal-safe: ``json.dumps`` escapes control bytes,
so a tenant-controlled note can never inject escape sequences into
the unit's journal through this path.

Exit contract: 0 when the sweep completed and the report printed
(per-tenant drive failures are IN the report per D-AC-3 — a broken
tenant instrument fails loud in its own record, never the sweep);
exit 2 when the sweep itself could not run (bad input / store
unwritable / internal error), one line on stderr, never a bare
traceback.
"""

import argparse
import json
import os
import sys

# Same invocation shape as the sibling CLIs: run from the checkout root
# as ``python3 -m hosted.relay_auto_driver_sweep`` so ``hosted`` is a
# package on sys.path.
from hosted import relay_auto_driver as driver
from hosted import relay_tenant_wiring as wiring
from hosted import tenant_status as ts


def build_parser():
    ap = argparse.ArgumentParser(
        description="Sweep every tenant's R3 wiring once (the scheduled "
                    "auto-driver path, #1723)."
    )
    ap.add_argument(
        "--store",
        required=True,
        help="tenant-record JSON store path (the same store the "
             "wiring's --tick CLI takes); the watermark sidecar lands "
             "next to it via watermark_path_for()",
    )
    ap.add_argument(
        "--journal-store-dir",
        default=None,
        help="fleet estate store dir whose events.jsonl receives one "
             "tick-note event per tenant (D-AC-4); omit to skip the "
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
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    store_path = os.path.abspath(args.store)
    if args.history:
        os.environ["RELAY_PROBE_HISTORY"] = args.history
    if args.journal:
        os.environ["RELAY_SESSION_JOURNAL"] = args.journal
    try:
        store = wiring.TenantFileWiringStore(ts.TenantStore(store_path))
        report = driver.tick_all_tenants(
            store,
            watermark_path=driver.watermark_path_for(store_path),
            journal_store_dir=args.journal_store_dir,
            journal_timeout_s=args.journal_timeout_s,
        )
    except Exception as exc:  # noqa: BLE001 - operator contract: one-line error, exit 2
        print(f"relay_auto_driver_sweep: error: {exc}", file=sys.stderr)
        return 2
    # json.dumps (not print-of-str) keeps tenant-controlled notes
    # terminal-safe in the unit's journal.
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
