#!/usr/bin/env python3
"""S3 packaging acceptance (issue #1723): the self-hosted cron/systemd
packaging for the relay auto-driver's scheduled sweep.

Pins the #1723 acceptance — "unit installs on a clean checkout, one
timer firing produces one applied tick per tenant in the watermark,
docs read by a cold operator":

1. Unit files are structurally sound and drive the S1 module through
   the sweep CLI (never ``--tick`` — D-AC-6).
2. The timer period equals the probe-cadence default (D-AC-1: one
   clock) — a default change that forgets the timer file fails here.
3. One subprocess firing of the sweep CLI against a REAL
   ``TenantFileWiringStore`` and the REAL producer instruments (probe
   history seeded with genuine ``relay_defect`` rows — no faked
   ``read_fn``) produces one applied tick per tenant in the F-AC-5
   watermark sidecar, ticks the fleet journal, and leaves the wiring's
   real suspension in the store (the report is not fabricated).
4. The operator doc exists and carries the sections a cold operator
   needs (install, cadence knob, output audience, sweep-vs---tick rule,
   the #1724 enablement gate).

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
import time

import pytest

from hosted import relay_auto_driver as driver
from hosted import relay_path_state as rps
from hosted import tenant_status as ts

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOSTED_DIR = os.path.dirname(os.path.abspath(__file__))
SERVICE = os.path.join(HOSTED_DIR, "relay-auto-driver.service")
TIMER = os.path.join(HOSTED_DIR, "relay-auto-driver.timer")
DOC = os.path.join(REPO_ROOT, "docs", "RELAY_AUTO_DRIVER_OPERATIONS.md")


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


def test_service_execstart_drives_sweep_module_not_tick():
    # D-AC-6: the scheduled path drives tick_all_tenants via the sweep
    # CLI — never --tick. Neuter: pointing ExecStart at the --tick CLI
    # fails.
    svc = _parse_systemd(_read(SERVICE))
    exec_start = svc["Service"].get("ExecStart", "")
    assert "-m hosted.relay_auto_driver_sweep" in exec_start
    assert "--tick" not in exec_start
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
    assert period_s == rps.DEFAULT_CADENCE_S == 300.0
    assert tmr["Install"].get("WantedBy") == "timers.target"
    assert tmr["Timer"].get("Persistent", "false").lower() == "false"


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


def _seed_probe_history(path):
    """Genuine producer evidence: two agreeing relay_defect rows per vm —
    the real relay_path_state maps them to a down reading (no fake
    read_fn anywhere on this path). Rows carry a fresh ts so the
    D-AC-2 staleness note stays quiet — this test drives the applied
    path, not the stale path."""
    now = time.time()
    with open(path, "w", encoding="utf-8") as fh:
        for i in range(2):
            fh.write(json.dumps(
                {"vm_id": "box-a", "outcome": "relay_defect",
                 "ts": now - i}) + "\n")


def test_cli_firing_produces_one_applied_tick_per_tenant(tmp_path):
    # The #1723 acceptance, executed: one timer firing == one sweep CLI
    # invocation against the real file store + the real producer.
    # Neuter: pointing the unit at relay_tenant_wiring --tick (the
    # pre-D-AC-6 plan) leaves the watermark sidecar empty and fails
    # the sidecar assertions below.
    store_path = str(tmp_path / "tenants.json")
    estate = tmp_path / "estate"
    estate.mkdir()
    history_path = str(tmp_path / "probe-history.jsonl")
    _seed_probe_history(history_path)

    store = ts.TenantStore(store_path)
    store.create(_tenant_record([_arc("box-a")], "tnt-a"))
    store.create(_tenant_record([_arc("box-a")], "tnt-b"))

    env = dict(os.environ)
    env["RELAY_PROBE_HISTORY"] = history_path
    # No RELAY_SESSION_JOURNAL: darkness — map_reading handles it as
    # down on relay_defect evidence.
    env.pop("RELAY_SESSION_JOURNAL", None)

    proc = subprocess.run(
        [sys.executable, "-m", "hosted.relay_auto_driver_sweep",
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
    assert set(report["tenants"]) == {"tnt-a", "tnt-b"}
    for tenant_id in ("tnt-a", "tnt-b"):
        rec = report["tenants"][tenant_id]
        assert rec["applied"] is True, \
            "tenant %r not applied: %r" % (tenant_id, rec)
        assert rec["events"] == 1
        assert rec["failed"] is False

    # The real wiring ran: each anchor's arc carries the relay-down
    # verdict (the report is not fabricated — the store carries it).
    for tenant_id in ("tnt-a", "tnt-b"):
        record = ts.TenantStore(store_path).get(tenant_id)
        arc = record.boxes["box-a"]
        assert arc.code == "connection-unreachable", \
            "tenant %r arc not driven: %r" % (tenant_id, arc.code)
        assert arc.latched == "live"

    # The F-AC-5 watermark sidecar landed next to the tenant store with
    # one applied tick per tenant.
    wm_path = driver.watermark_path_for(store_path)
    assert os.path.isfile(wm_path), "watermark sidecar missing: %s" % wm_path
    with open(wm_path, encoding="utf-8") as fh:
        sidecar = json.load(fh)
    assert set(sidecar) == {"tnt-a", "tnt-b"}
    for tenant_id in ("tnt-a", "tnt-b"):
        assert sidecar[tenant_id]["applied"] is True

    # The D-AC-4 journal leg: one tick-note event per tenant in the
    # estate's events.jsonl.
    journal_path = os.path.join(str(estate), "events.jsonl")
    with open(journal_path, encoding="utf-8") as fh:
        events = [json.loads(line) for line in fh if line.strip()]
    assert len(events) == 2, "expected 2 tick-note events, got %d" % len(events)


def test_cli_bad_store_exits_two_one_line(tmp_path):
    # Operator contract: the sweep itself failing is loud and
    # non-zero, never a bare traceback. A store path that is a
    # directory (not a JSON file) fails the store read loudly.
    # Neuter: returning 0 here fails.
    proc = subprocess.run(
        [sys.executable, "-m", "hosted.relay_auto_driver_sweep",
         "--store", str(tmp_path)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 2
    assert proc.stderr.startswith("relay_auto_driver_sweep: error: ")
    assert "Traceback" not in proc.stderr


def test_cli_missing_store_arg_exits_two(tmp_path):
    # --store is required (argparse contract).
    proc = subprocess.run(
        [sys.executable, "-m", "hosted.relay_auto_driver_sweep"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 2


# ---------------------------------------------------------------------------
# Operator doc carries the cold-operator contract


def _doc():
    return _read(DOC)


def test_ops_doc_sections():
    # A cold operator needs: install, the cadence knob, where output
    # goes, the sweep-vs---tick rule, and the #1724 enablement gate.
    # Neuter: deleting any section header fails.
    doc = _doc()
    for section in ("## 1. Install",
                    "## 2. The cadence knob",
                    "## 3. Where the output goes",
                    "## 4. The scheduled sweep vs manual `--tick`",
                    "## 5. Failure posture",
                    "## 6. Trust note"):
        assert section in doc, "ops doc missing %r" % section


def test_ops_doc_pins_the_contracts():
    doc = _doc()
    # The knob by name, the sidecar by name, the journal by name.
    assert "RELAY_PROBE_CADENCE_S" in doc
    assert ".relay-tick-watermarks.json" in doc
    assert "events.jsonl" in doc
    # The D-AC-6 never-scheduled---tick rule, verbatim-discoverable.
    assert "never" in doc.lower() and "--tick" in doc
    # The D-AC-6 sequencing: the timer stays disabled until the S4
    # staleness alert lands. Neuter: deleting the gate fails.
    assert "#1724" in doc
    assert "do NOT enable the timer until #1724" in doc
