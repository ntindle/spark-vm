"""Tests for the fleet event<->inventory cross-check (G17 S2, #779).

Run from the repo root:  python3 -m pytest fleet/test_crosscheck.py -q

All tests run locally with no network and no home-dir writes: the two
journals are written directly into a tmp store dir, and the CLI is
exercised through subprocess, never imported. The cross-check consumes
collector-side clocks (event `received_at`, record `observed_at`) —
box clocks are never trusted — so every fixture stamps both
explicitly.

Anti-vacuity: the verdict tests pin the exact verdict word on the verdict
*row* (anchored `^  box verdict` — the summary's "N confirmed" counts also
carry the verdict words, so a bare substring match would pass against the
wrong row) and the exit code, so an implementation that always-confirms,
always-violates, or treats silence as a violation fails its counter-test
below. The "missing evidence is never a violation" rule is pinned by the
inconclusive_* tests.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone

import pytest

FLEET = os.path.dirname(os.path.abspath(__file__))
EVENTS = os.path.join(FLEET, "events.py")
INVENTORY = os.path.join(FLEET, "inventory.py")

BASE = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
COMMIT_A = "a" * 40
COMMIT_B = "b" * 40


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def run_cli(*argv):
    return subprocess.run(
        [sys.executable, EVENTS, *argv],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def run_wired(*argv):
    """The inventory.py-wired entry (`fleet events crosscheck`)."""
    return subprocess.run(
        [sys.executable, INVENTORY, *argv],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


@pytest.fixture()
def store():
    with tempfile.TemporaryDirectory() as tmp:
        yield tmp


def write_events(store, events):
    path = os.path.join(store, "events.jsonl")
    with open(path, "w", encoding="utf-8") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")


def write_records(store, records):
    path = os.path.join(store, "journal.jsonl")
    with open(path, "w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")


def claim(box, to, received, event_id=None, **extra):
    e = {"box_id": box, "event_id": event_id or ("ev-" + box + "-"
                                               + (to[:4] if to else "none")),
         "kind": "deploy", "outcome": "succeeded", "component": "repo",
         "to": to, "received_at": iso(received)}
    e.update(extra)
    return e


def record(box, commit, observed):
    return {"box_id": box, "observed_at": iso(observed),
            "versions": {"repo_commit": commit, "toolset_pins": None,
                         "image_version": None}}


# --- Verdicts ---------------------------------------------------------------
#
# Verdict assertions are anchored to the row line (^  box verdict) — the
# summary's "N confirmed / N violation / N inconclusive" counts also carry
# the verdict words, so a bare substring match would pass against the
# wrong row (e.g. "confirmed" matches the summary's "0 confirmed" while
# the row itself says inconclusive).

def row_verdict(out, box, verdict):
    return re.search(r"^  %s\s+%s\s" % (re.escape(box), verdict), out,
                     re.M) is not None


def test_confirmed_claim(store):
    received = BASE
    write_events(store, [claim("tower", COMMIT_B, received)])
    write_records(store, [record("tower", COMMIT_B, received + timedelta(minutes=30))])
    proc = run_cli("--store", store, "crosscheck")
    assert proc.returncode == 0, proc.stderr
    assert row_verdict(proc.stdout, "tower", "confirmed")
    assert re.search(r"^summary: .*0 violation\(s\)", proc.stdout, re.M)


def test_boundary_observation_at_claim_time_counts(store):
    # The at-or-after rule is inclusive: an observation at exactly the
    # claim's received_at is a valid later observation.
    write_events(store, [claim("tower", COMMIT_B, BASE)])
    write_records(store, [record("tower", COMMIT_B, BASE),
                          record("tower", COMMIT_A, BASE + timedelta(minutes=30))])
    proc = run_cli("--store", store, "crosscheck")
    assert proc.returncode == 0, proc.stderr
    assert row_verdict(proc.stdout, "tower", "confirmed")


def test_boundary_observation_at_claim_time_can_violate(store):
    write_events(store, [claim("tower", COMMIT_B, BASE)])
    write_records(store, [record("tower", COMMIT_A, BASE)])
    proc = run_cli("--store", store, "crosscheck")
    assert proc.returncode == 1, proc.stderr
    assert row_verdict(proc.stdout, "tower", "violation")


def test_violation_when_later_inventory_disagrees(store):
    received = BASE
    write_events(store, [claim("tower", COMMIT_B, received)])
    write_records(store, [record("tower", COMMIT_A, received + timedelta(minutes=30))])
    proc = run_cli("--store", store, "crosscheck")
    assert proc.returncode == 1, proc.stderr
    out = proc.stdout
    assert row_verdict(out, "tower", "violation")
    assert "tower" in out
    assert "VIOLATIONS are flags, not convictions" in out


def test_inconclusive_when_inventory_is_older_than_claim(store):
    # Silence (no later observation) is missing evidence, never a
    # violation — the rule that keeps an un-collected box from paging.
    received = BASE
    write_events(store, [claim("tower", COMMIT_B, received)])
    write_records(store, [record("tower", COMMIT_B, received - timedelta(hours=1))])
    proc = run_cli("--store", store, "crosscheck")
    assert proc.returncode == 0, proc.stderr
    assert row_verdict(proc.stdout, "tower", "inconclusive")


def test_inconclusive_when_later_record_reports_no_commit(store):
    received = BASE
    write_events(store, [claim("tower", COMMIT_B, received)])
    write_records(store, [record("tower", None, received + timedelta(minutes=30))])
    proc = run_cli("--store", store, "crosscheck")
    assert proc.returncode == 0, proc.stderr
    assert row_verdict(proc.stdout, "tower", "inconclusive")


def test_inconclusive_when_box_has_no_records(store):
    write_events(store, [claim("tower", COMMIT_B, BASE)])
    write_records(store, [record("other", COMMIT_B, BASE + timedelta(minutes=30))])
    proc = run_cli("--store", store, "crosscheck")
    assert proc.returncode == 0, proc.stderr
    assert row_verdict(proc.stdout, "tower", "inconclusive")


def test_inconclusive_when_claim_is_unattributable(store):
    ev = claim("tower", COMMIT_B, BASE)
    ev["box_id"] = None
    write_events(store, [ev])
    write_records(store, [record("tower", COMMIT_B, BASE + timedelta(minutes=30))])
    proc = run_cli("--store", store, "crosscheck")
    assert proc.returncode == 0, proc.stderr
    assert "inconclusive" in proc.stdout


def test_violation_and_later_confirmation_both_reported(store):
    # A violated claim stays visible in the report even when the box
    # later converges: the report is a verdict series, not a latest-only
    # rollup.
    write_events(store, [
        claim("tower", COMMIT_B, BASE, event_id="ev-bad"),
        claim("tower", COMMIT_A, BASE + timedelta(hours=1), event_id="ev-good"),
    ])
    write_records(store, [
        record("tower", COMMIT_A, BASE + timedelta(minutes=30)),
        record("tower", COMMIT_A, BASE + timedelta(hours=2)),
    ])
    proc = run_cli("--store", store, "crosscheck")
    assert proc.returncode == 1, proc.stderr
    out = proc.stdout
    assert row_verdict(out, "tower", "violation")
    assert row_verdict(out, "tower", "confirmed")
    assert "1 checked" not in out  # both claims evaluated, not rolled up


def test_box_filter_scopes_verdicts(store):
    write_events(store, [
        claim("tower", COMMIT_B, BASE),
        claim("shed", COMMIT_B, BASE),
    ])
    write_records(store, [
        record("tower", COMMIT_A, BASE + timedelta(minutes=30)),
        record("shed", COMMIT_B, BASE + timedelta(minutes=30)),
    ])
    proc_all = run_cli("--store", store, "crosscheck")
    assert proc_all.returncode == 1, proc_all.stderr
    proc_shed = run_cli("--store", store, "--box", "shed", "crosscheck")
    assert proc_shed.returncode == 0, proc_shed.stderr
    assert row_verdict(proc_shed.stdout, "shed", "confirmed")


def test_non_claim_events_are_ignored(store):
    # failed / precheck-fail / rollback-failed are not claims about what
    # is running — they must not produce verdict rows.
    write_events(store, [
        claim("tower", COMMIT_B, BASE, outcome="failed"),
        claim("tower", COMMIT_B, BASE, outcome="precheck-fail",
              event_id="ev-pre"),
        {"box_id": "tower", "event_id": "ev-rb", "kind": "deploy",
         "outcome": "rollback-failed", "component": "repo", "to": COMMIT_B,
         "received_at": iso(BASE)},
    ])
    write_records(store, [record("tower", COMMIT_A, BASE + timedelta(minutes=30))])
    proc = run_cli("--store", store, "crosscheck")
    assert proc.returncode == 0, proc.stderr
    assert "no checkable claims" in proc.stdout


def test_claim_without_to_is_inconclusive(store):
    write_events(store, [claim("tower", None, BASE)])
    write_records(store, [record("tower", COMMIT_B, BASE + timedelta(minutes=30))])
    proc = run_cli("--store", store, "crosscheck")
    assert proc.returncode == 0, proc.stderr
    assert row_verdict(proc.stdout, "tower", "inconclusive")


def test_claim_with_unparseable_received_at_is_inconclusive(store):
    write_events(store, [claim("tower", COMMIT_B, BASE,
                               received_at="not-a-timestamp")])
    write_records(store, [record("tower", COMMIT_A, BASE + timedelta(minutes=30))])
    proc = run_cli("--store", store, "crosscheck")
    assert proc.returncode == 0, proc.stderr
    assert row_verdict(proc.stdout, "tower", "inconclusive")


def test_malformed_journal_lines_do_not_crash(store):
    with open(os.path.join(store, "events.jsonl"), "w",
              encoding="utf-8") as fh:
        fh.write("this is not json\n")
        fh.write(json.dumps(claim("tower", COMMIT_B, BASE)) + "\n")
        fh.write(json.dumps(["a", "list", "not", "a", "dict"]) + "\n")
    with open(os.path.join(store, "journal.jsonl"), "w",
              encoding="utf-8") as fh:
        fh.write("{broken\n")
        fh.write(json.dumps(record("tower", COMMIT_B,
                                   BASE + timedelta(minutes=30))) + "\n")
    proc = run_cli("--store", store, "crosscheck")
    assert proc.returncode == 0, proc.stderr
    assert row_verdict(proc.stdout, "tower", "confirmed")


def test_empty_store_reports_no_claims(store):
    proc = run_cli("--store", store, "crosscheck")
    assert proc.returncode == 0, proc.stderr
    assert "no checkable claims" in proc.stdout
    assert "verdict" not in proc.stdout  # no dangling column header


def test_nonexistent_store_exits_2(store):
    # A typo'd or unmounted store path must fail loudly, never report
    # a clean bill of health after reading nothing.
    missing = os.path.join(store, "does-not-exist")
    proc = run_cli("--store", missing, "crosscheck")
    assert proc.returncode == 2, proc.stderr
    assert "not found" in proc.stderr


def test_nonexistent_store_exits_2_wired(store):
    missing = os.path.join(store, "does-not-exist")
    proc = run_wired("events", "crosscheck", "--store", missing)
    assert proc.returncode == 2, proc.stderr
    assert "not found" in proc.stderr


def test_wired_into_inventory_events_cli(store):
    write_events(store, [claim("tower", COMMIT_B, BASE)])
    write_records(store, [record("tower", COMMIT_A, BASE + timedelta(minutes=30))])
    proc = run_wired("events", "crosscheck", "--store", store)
    assert proc.returncode == 1, proc.stderr
    assert row_verdict(proc.stdout, "tower", "violation")
    assert "tower" in proc.stdout


def test_box_filter_wired_into_inventory_cli(store):
    write_events(store, [claim("shed", COMMIT_B, BASE)])
    write_records(store, [record("shed", COMMIT_B, BASE + timedelta(minutes=30))])
    proc = run_wired("events", "crosscheck", "--store", store, "--box", "shed")
    assert proc.returncode == 0, proc.stderr
    assert row_verdict(proc.stdout, "shed", "confirmed")


def test_violation_summary_counts(store):
    write_events(store, [
        claim("tower", COMMIT_B, BASE, event_id="ev-v"),
        claim("shed", COMMIT_B, BASE, event_id="ev-c"),
    ])
    write_records(store, [
        record("tower", COMMIT_A, BASE + timedelta(minutes=30)),
        record("shed", COMMIT_B, BASE + timedelta(minutes=30)),
    ])
    proc = run_cli("--store", store, "crosscheck")
    out = proc.stdout
    assert "2 checked" in out
    assert "1 confirmed" in out
    assert "1 violation" in out
