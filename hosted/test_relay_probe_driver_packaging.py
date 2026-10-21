#!/usr/bin/env python3
"""S5 packaging acceptance (issue #1837): the self-hosted cron/systemd
packaging for the relay probe driver's scheduled sweep.

Pins the #1837 acceptance — "unit installs on a clean checkout, one
timer firing produces one probe-tick record per tenant in the probe
watermark, docs read by a cold operator":

1. Unit files are structurally sound and drive the S5 module through
   the sweep CLI (never ``--tick`` or ``--probe-now`` — the scheduled
   path is the sweep; the manual paths are per-tenant/per-vm).
2. The timer period equals the probe-cadence default (D-AC-1: one
   clock) — a default change that forgets the timer file fails here.
3. One subprocess firing of the sweep CLI against a REAL
   ``TenantFileWiringStore`` and the REAL producer instruments (no
   faked read_fn, no bundle supplier — the dark-instrument steady
   state) produces one probe-tick record per tenant in the probe
   watermark sidecar, ticks the fleet journal, and leaves the
   dark-instrument LOUD note on each record (the report is not
   fabricated).
4. The operator doc exists and carries the sections a cold operator
   needs (install, cadence knob, output audience, sweep-vs-manual
   rule, the #1724 enablement gate).

Every test asserts a concrete transition or record — none pass
vacuously (each was neuter-verified: the corresponding file/content
revert fails the test; see per-test notes).
"""

import json
import os
import re
import subprocess
import sys
import tempfile

import pytest

from hosted import relay_path_state as rps
from hosted import relay_probe_driver as pdriver
from hosted import tenant_status as ts

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOSTED_DIR = os.path.dirname(os.path.abspath(__file__))
SERVICE = os.path.join(HOSTED_DIR, "relay-probe-driver.service")
TIMER = os.path.join(HOSTED_DIR, "relay-probe-driver.timer")
DOC = os.path.join(REPO_ROOT, "docs", "RELAY_PROBE_DRIVER_OPERATIONS.md")


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _parse_systemd(text):
    """Minimal ini parse: {section: {key: value}} (last wins)."""
    sections = {}
    current = None
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(("#", ";")):
            continue
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1]
            sections.setdefault(current, {})
        elif current is not None and "=" in line:
            key, _, value = line.partition("=")
            sections[current][key.strip()] = value.strip()
    return sections


def _period_to_seconds(value):
    m = re.fullmatch(r"(\d+)\s*(s|sec|secs|m|min|mins|h|hr|hrs)?", value.strip())
    assert m, "unparseable systemd time span %r" % (value,)
    factor = {"s": 1, "sec": 1, "secs": 1, None: 1,
              "m": 60, "min": 60, "mins": 60,
              "h": 3600, "hr": 3600, "hrs": 3600}[m.group(2)]
    return int(m.group(1)) * factor


# ---------------------------------------------------------------------------
# Unit-file structure


def test_service_file_sections_and_oneshot():
    # Neuter: dropping the [Service] section (or changing Type) fails.
    svc = _parse_systemd(_read(SERVICE))
    for section in ("Unit", "Service", "Install"):
        assert section in svc, "service file missing [%s]" % section
    assert svc["Service"].get("Type") == "oneshot"
    assert svc["Install"].get("WantedBy") == "multi-user.target"


def test_service_execstart_drives_probe_sweep_module_not_manual():
    # #1837: the scheduled path drives probe_all_tenants via the probe
    # sweep CLI — never --tick (the drive path) or --probe-now (the
    # per-vm manual path). Neuter: pointing ExecStart at either manual
    # CLI fails.
    svc = _parse_systemd(_read(SERVICE))
    exec_start = svc["Service"].get("ExecStart", "")
    assert "-m hosted.relay_probe_driver_sweep" in exec_start
    assert "--tick" not in exec_start
    assert "--probe-now" not in exec_start
    assert "--store" in exec_start
    # The sweep's stdout is the raw report for the unit's journal
    # (D-AC-4: watermark + fleet journal are the durable observability).
    assert svc["Service"].get("StandardOutput") == "journal"
    assert svc["Service"].get("StandardError") == "journal"


def test_service_install_time_templating_pinned():
    # The unit ships with install-time placeholders, never a hardcoded
    # operator path. Neuter: hardcoding a real path fails.
    text = _read(SERVICE)
    for placeholder in ("<CHECKOUT>", "<TENANT_STORE>",
                        "<ESTATE_STORE_DIR>", "<BOX_OWNER>"):
        assert placeholder in text, "missing template placeholder %s" % placeholder
    assert "/home/" not in text and "/root/" not in text, \
        "service file hardcodes an operator path"


def test_timer_period_matches_probe_cadence_default():
    # D-AC-1 — one clock: the timer period IS the probe cadence. The
    # driver reads cadence_s() (RELAY_PROBE_CADENCE_S, default
    # DEFAULT_CADENCE_S); the timer must fire at the same default, or
    # the "one clock" pin is a lie in packaging. Neuter: changing
    # OnUnitActiveSec to 10min fails.
    tmr = _parse_systemd(_read(TIMER))
    assert "Timer" in tmr and "Install" in tmr
    period_s = _period_to_seconds(tmr["Timer"]["OnUnitActiveSec"])
    assert period_s == rps.DEFAULT_CADENCE_S
    assert tmr["Install"].get("WantedBy") == "timers.target"
    assert tmr["Timer"].get("Persistent", "false").lower() == "false"


def test_service_pins_pathology_budget_inside_firing_period():
    # #1836 (mirrored from the S3 unit): the unit pins an explicit
    # pathology budget, and the budget must fit inside the firing
    # period or wedged sweeps pile up across timer firings.
    # Neuter: deleting TimeoutStartSec, or raising it to 10min, fails.
    svc = _parse_systemd(_read(SERVICE))
    tmr = _parse_systemd(_read(TIMER))
    raw = svc["Service"].get("TimeoutStartSec")
    assert raw, "service file pins no TimeoutStartSec (#1836)"
    budget_s = _period_to_seconds(raw)
    assert budget_s == 240, \
        "pathology budget changed from 240s without updating the pin: %r" % raw
    period_s = _period_to_seconds(tmr["Timer"]["OnUnitActiveSec"])
    assert budget_s < period_s, \
        "pathology budget %ds must fit inside the firing period %ds" \
        % (budget_s, period_s)


def test_service_execstart_bounds_journal_lock_wait():
    # #1836 (mirrored from the S3 unit): the per-box journal-lock wait
    # is tick-scale on the scheduled path, not the 300s fleet default —
    # a wedged journal lock fails loud per tenant after seconds instead
    # of stalling the sweep up to 5 minutes per box instrument.
    # Neuter: dropping --journal-timeout-s from ExecStart fails.
    svc = _parse_systemd(_read(SERVICE))
    exec_start = svc["Service"].get("ExecStart", "")
    m = re.search(r"--journal-timeout-s\s+(\d+(?:\.\d+)?)", exec_start)
    assert m, "ExecStart sets no --journal-timeout-s (#1836)"
    bound = float(m.group(1))
    assert 0 < bound <= 60, \
        "journal-lock bound %ss is not tick-scale (want seconds, not minutes)" % bound


# ---------------------------------------------------------------------------
# One firing end-to-end through the real producer instruments


def _arc(box_id="box-a"):
    return ts.BoxArc(box_id=box_id, created_at="2026-10-01T00:00:00Z",
                     code="live", relay_reachable=True,
                     provider_running=True)


def _tenant_record(boxes, tenant_id):
    return ts.TenantRecord(
        tenant_id=tenant_id,
        stage=2,
        approvals_url="https://approve.example/a/%s" % tenant_id,
        boxes={b.box_id: b for b in boxes},
    )


def test_cli_firing_produces_one_probe_tick_per_tenant(tmp_path):
    # The #1837 acceptance, executed: one timer firing == one sweep CLI
    # invocation against the real file store + the real producer. No
    # bundle supplier is wired (D-RL2-3): the dark-instrument steady
    # state is the honest assertion — each record carries the LOUD
    # no-bundle note, probed=False, failed=False, and the probe
    # watermark + journal still land.
    # Neuter: pointing the unit at relay_tenant_wiring --tick (the
    # pre-D-AC-6-style mistake) leaves the probe watermark sidecar
    # empty and fails the sidecar assertions below.
    store_path = str(tmp_path / "tenants.json")
    estate = tmp_path / "estate"
    estate.mkdir()
    history_path = str(tmp_path / "probe-history.jsonl")

    store = ts.TenantStore(store_path)
    store.create(_tenant_record([_arc("box-a")], "tnt-a"))
    store.create(_tenant_record([_arc("box-a")], "tnt-b"))

    env = dict(os.environ)
    env["RELAY_PROBE_HISTORY"] = history_path
    env.pop("RELAY_SESSION_JOURNAL", None)

    proc = subprocess.run(
        [sys.executable, "-m", "hosted.relay_probe_driver_sweep",
         "--store", store_path,
         "--journal-store-dir", str(estate)],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, "sweep failed: %s" % proc.stderr
    report = json.loads(proc.stdout)
    assert report["errors"] == [], \
        "clean sweep should carry no errors[] entries: %r" % report["errors"]
    assert set(report["tenants"]) == {"tnt-a", "tnt-b"}
    for tenant_id in ("tnt-a", "tnt-b"):
        rec = report["tenants"][tenant_id]
        assert rec["failed"] is False, \
            "tenant %r failed: %r" % (tenant_id, rec)
        assert rec["probed"] is False
        assert rec["stand_down"] is False
        # Dark-instrument honesty: no bundle wired, so the due tick is
        # noted LOUD, not failed.
        assert any("no bundle supplied" in n for n in rec["notes"]), \
            "tenant %r missing the dark-instrument note: %r" % (tenant_id, rec["notes"])

    # The probe watermark sidecar landed next to the tenant store with
    # one probe-tick record per tenant (distinct from the drive
    # watermark — S4's fail-visible story).
    wm_path = pdriver.probe_watermark_path_for(store_path)
    assert os.path.isfile(wm_path), "probe watermark sidecar missing: %s" % wm_path
    with open(wm_path, encoding="utf-8") as fh:
        sidecar = json.load(fh)
    assert set(sidecar) == {"tnt-a", "tnt-b"}
    for tenant_id in ("tnt-a", "tnt-b"):
        assert sidecar[tenant_id]["probed"] is False

    # The D-AC-4 journal leg: one probe-note event per tenant in the
    # estate's events.jsonl.
    journal_path = os.path.join(str(estate), "events.jsonl")
    with open(journal_path, encoding="utf-8") as fh:
        events = [json.loads(line) for line in fh if line.strip()]
    assert len(events) == 2, "expected 2 probe-note events, got %d" % len(events)


def test_cli_bad_store_exits_two_one_line(tmp_path):
    # Operator contract: the sweep itself failing is loud and
    # non-zero, never a bare traceback. A store path that is a
    # directory (not a JSON file) fails the store read loudly.
    # Neuter: returning 0 here fails.
    proc = subprocess.run(
        [sys.executable, "-m", "hosted.relay_probe_driver_sweep",
         "--store", str(tmp_path)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 2, "expected exit 2, got %d: %s" % (
        proc.returncode, proc.stderr)
    assert "relay_probe_driver_sweep: error:" in proc.stderr
    assert "Traceback" not in proc.stderr


# ---------------------------------------------------------------------------
# Operator doc


def test_operator_doc_carries_cold_operator_sections():
    # The cold operator needs: install, the cadence knob, the output
    # audience, the sweep-vs-manual rule, and the #1724 enablement
    # gate. Neuter: deleting any section fails.
    doc = _read(DOC)
    for needle in ("## 1. Install", "## 2. The cadence knob",
                   "## 3. Output audience", "sweep-vs-manual",
                   "#1724", "relay-probe-driver.service"):
        assert needle in doc, "operator doc missing %r" % needle


def test_operator_doc_documents_pathology_budget():
    # #1836 (mirrored from the S3 unit): the pathology budget is an
    # operator-visible contract — a cold operator reading §5 must find
    # the TimeoutStartSec bound and the tick-scale journal-lock wait,
    # and why a killed sweep is signaled by a missing watermark rather
    # than a LOUD record. Neuter: deleting the §5 bound bullet fails.
    doc = _read(DOC)
    assert "TimeoutStartSec=240s" in doc
    assert "--journal-timeout-s 30" in doc
    assert "#1836" in doc
    # The inert --provider-state flag is disclosed honestly: it does
    # nothing until a bundle supplier is wired.
    assert "inert until a bundle supplier is wired" in doc
