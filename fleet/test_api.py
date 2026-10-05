"""Conformance tests for fleet/api.py (G21 S1, issue #795).

Per docs/FLEET_READ_API_SPEC.md §4, every endpoint ships a conformance
test: build a store fixture, run the real `fleet` CLI renderer, call the
API (through the real HTTP path — an in-process localhost server on an
ephemeral port), and assert field-equivalence: every field the CLI
renders appears in the API response with the same value and the same
ordering, plus the documented full-value companions.

Run from the repo root:  python3 -m pytest fleet/test_api.py -q

All tests run locally with no network and no home-dir writes: the store
lives under a tmp dir, the API server binds 127.0.0.1 with an ephemeral
port, and the CLIs are exercised through subprocess, never imported.
"""

import io
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import urllib.request
import urllib.error
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from http.server import HTTPServer

import pytest

FLEET = os.path.dirname(os.path.abspath(__file__))
INVENTORY = os.path.join(FLEET, "inventory.py")
sys.path.insert(0, FLEET)
import api  # noqa: E402  (fleet/ is not a package; same-dir import)

NOW = datetime.now(timezone.utc).replace(microsecond=0)
COMMIT_A = "a" * 40
COMMIT_B = "b" * 40
COMMIT_C = "c" * 40
COMMIT_F = "f" * 40

EVIL_NOTE = "deployed\x1b[31mred\x1b[0m\nforged line"
EVIL_DETAIL = "box said\x00bad\x1b[2Kthings"


def run_cli(*argv):
    return subprocess.run(
        [sys.executable, INVENTORY, *argv],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def _inv_record(box_id, observed_at, commit=None, toolset=None, deploy=None,
                frozen=None, suspect=False, suspect_reason=None):
    versions = {"repo_commit": commit} if commit else {}
    tick = {}
    if toolset:
        tick["toolset"] = toolset
    if deploy:
        tick["deploy"] = deploy
    return {"box_id": box_id, "observed_at": observed_at.isoformat(),
            "versions": versions, "last_tick_at": tick,
            "gate": {"frozen": frozen}, "suspect": suspect,
            "suspect_reason": suspect_reason}


def _event(event_id, box_id, kind, outcome, frm, to, emitted_at, received_at,
           note="", subcomponent="repo"):
    return {"event_id": event_id, "box_id": box_id,
            "session_epoch": 1,
            "emitted_at": emitted_at.isoformat(),
            "received_at": received_at.isoformat(),
            "source": "audit-tail", "component": "repo",
            "subcomponent": subcomponent, "subcomponents": [subcomponent],
            "kind": kind, "outcome": outcome, "from": frm, "to": to,
            "phase": "deploy", "rollout": None, "trigger": "cron",
            "attested": False, "note": note}


def _alert(alert_id, rule, box_id, fired_at, detail, acked=False):
    return {"alert_id": alert_id, "rule": rule, "box_id": box_id,
            "subcomponent": "repo", "to": COMMIT_A,
            "fired_at": fired_at.isoformat(), "detail": detail,
            "acked": acked}


@pytest.fixture()
def store():
    """Fixture store: inventory journal + real rebuilt snapshot, plus
    hand-written event/alert journals (plain JSONL, the readers' input
    contract)."""
    with tempfile.TemporaryDirectory() as root:
        store_dir = os.path.join(root, "store")
        os.makedirs(store_dir)
        journal = [
            _inv_record("box-a", NOW - timedelta(hours=3), COMMIT_A,
                        toolset="2026-10-04T11:00:00Z",
                        deploy="2026-10-04T11:05:00Z-long-tail"),
            _inv_record("box-a", NOW - timedelta(hours=1), COMMIT_A,
                        toolset="2026-10-04T13:00:00Z",
                        deploy="2026-10-04T13:05:00Z-long-tail"),
            _inv_record("box-a", NOW, COMMIT_A,
                        toolset="2026-10-04T14:00:00Z",
                        deploy="2026-10-04T14:05:00Z-long-tail"),
            _inv_record("box-b", NOW - timedelta(hours=1), COMMIT_B,
                        toolset="2026-10-04T13:30:00Z",
                        frozen=True, suspect=True,
                        suspect_reason="flaky self-report"),
            _inv_record("box-c", NOW - timedelta(hours=30), COMMIT_C,
                        toolset="2026-10-03T08:00:00Z"),
            _inv_record("box-d", NOW - timedelta(minutes=30)),
        ]
        with open(os.path.join(store_dir, "journal.jsonl"), "w") as fh:
            for record in journal:
                fh.write(json.dumps(record) + "\n")
        proc = run_cli("rebuild", "--store", store_dir)
        assert proc.returncode == 0, proc.stderr

        events = [
            _event("e1", "box-a", "deploy", "succeeded", COMMIT_C, COMMIT_A,
                   NOW - timedelta(hours=3), NOW - timedelta(hours=2),
                   note=EVIL_NOTE),
            _event("e2", "box-a", "deploy", "succeeded", COMMIT_A, COMMIT_A,
                   NOW - timedelta(hours=1),
                   NOW - timedelta(minutes=50), note="steady"),
            # Inconclusive crosscheck claim: received_at is newer than any
            # inventory observation (missing evidence, not a violation).
            _event("e3", "box-a", "deploy", "succeeded", COMMIT_A, COMMIT_A,
                   NOW - timedelta(minutes=10), NOW + timedelta(hours=1),
                   note="future claim"),
            _event("e4", "box-b", "deploy", "failed", COMMIT_B, COMMIT_F,
                   NOW - timedelta(hours=1),
                   NOW - timedelta(minutes=55), note="boom"),
            # Violation crosscheck claim: box-b's later inventory shows
            # COMMIT_B, never the claimed COMMIT_F.
            _event("e5", "box-b", "deploy", "succeeded", COMMIT_B, COMMIT_F,
                   NOW - timedelta(hours=2),
                   NOW - timedelta(hours=2, minutes=-30), note="liar"),
        ]
        with open(os.path.join(store_dir, "events.jsonl"), "w") as fh:
            for event in events:
                fh.write(json.dumps(event) + "\n")
        alerts = [
            _alert("alert-1", "rule-2-stuck", "box-a",
                   NOW - timedelta(hours=2), EVIL_DETAIL),
            _alert("alert-2", "rule-1-rollback", "box-b",
                   NOW - timedelta(hours=1), "old news", acked=True),
        ]
        with open(os.path.join(store_dir, "alerts.jsonl"), "w") as fh:
            for alert in alerts:
                fh.write(json.dumps(alert) + "\n")
        yield store_dir


@contextmanager
def api_server(store_dir):
    """The real HTTP path: in-process localhost server, ephemeral port."""
    api.FleetAPIHandler.store_dir = store_dir
    server = HTTPServer(("127.0.0.1", 0), api.FleetAPIHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield "http://127.0.0.1:%d" % server.server_address[1]
    finally:
        server.shutdown()
        thread.join()


def get(base, path):
    url = base + path
    try:
        with urllib.request.urlopen(url) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8")), \
                resp.headers.get("Content-Type")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8")), \
            exc.headers.get("Content-Type")


def post(base, path):
    req = urllib.request.Request(base + path, data=b"{}", method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def raw_method(base, path, method):
    # Every response the API speaks is JSON, even for refused verbs.
    req = urllib.request.Request(base + path, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


# --- /fleet/boxes ------------------------------------------------------

def test_boxes_conformance(store):
    proc = run_cli("inventory", "--store", store, "--staleness-hours", "24")
    assert proc.returncode == 0, proc.stderr
    lines = proc.stdout.splitlines()
    header_idx = next(i for i, l in enumerate(lines)
                      if l.startswith("box ") or l.startswith("box"))
    data_lines = []
    for line in lines[header_idx + 1:]:
        if not line.strip() or line.startswith("census"):
            break
        data_lines.append(line)
    cli_rows = []
    for line in data_lines:
        m = re.match(r"(\S+)\s+(\(no report\)|\S+)\s+(\S+)\s+"
                     r"(\S+)\s+(.*)$", line)
        assert m, line
        cli_rows.append(m.groups())

    census_line = next(l for l in lines if l.startswith("census (eligible"))
    m = re.match(r"census \(eligible (\d+) of (\d+) boxes; (\d+) stale, "
                 r"excluded\):", census_line)
    eligible, total, stale = map(int, m.groups())
    cli_per_commit = []
    for line in lines[lines.index(census_line) + 1:]:
        m = re.match(r"  (\(no report\)|\S+): (\d+)/(\d+) boxes "
                     r"\(([\d.]+)%\)", line)
        if not m:
            break
        cli_per_commit.append((m.group(1), int(m.group(2)),
                               float(m.group(4))))

    with api_server(store) as base:
        status, body, ctype = get(base, "/fleet/boxes?staleness_hours=24")
    assert status == 200
    assert ctype == "application/json"

    assert [(r["box_id"], r["repo_commit"], r["toolset_tick"],
             "yes" if r["frozen"] is True
             else "no" if r["frozen"] is False else "n/a",
             ",".join(r["flags"]) or "-") for r in body["boxes"]] == \
        [(bid, commit, tick, frozen, flags)
         for bid, commit, tick, frozen, flags in cli_rows]
    assert [r["eligible"] for r in body["boxes"]] == \
        ["stale" not in flags.split(",")
         for _, _, _, _, flags in cli_rows]
    assert body["census"]["eligible"] == eligible
    assert body["census"]["total"] == total
    assert body["census"]["stale"] == stale
    assert [(p["commit"], p["count"], round(p["pct"], 1))
            for p in body["census"]["per_commit"]] == \
        [(c, n, pct) for c, n, pct in cli_per_commit]
    assert body["staleness_hours"] == 24
    assert body["data_current_as_of"]  # snapshot generated_at
    # Full companions travel alongside the display truncations (§4).
    box_a = next(r for r in body["boxes"] if r["box_id"] == "box-a")
    assert box_a["repo_commit"] == COMMIT_A[:12]
    assert box_a["repo_commit_full"] == COMMIT_A
    assert box_a["toolset_tick"] == "2026-10-04"[:10]
    assert box_a["toolset_tick_full"] == "2026-10-04T14:00:00Z"
    box_d = next(r for r in body["boxes"] if r["box_id"] == "box-d")
    assert box_d["repo_commit"] == "(no report)"
    assert box_d["repo_commit_full"] is None
    assert box_d["flags"] == []
    box_b = next(r for r in body["boxes"] if r["box_id"] == "box-b")
    assert box_b["flags"] == ["suspect"]
    assert box_b["frozen"] is True
    box_c = next(r for r in body["boxes"] if r["box_id"] == "box-c")
    assert box_c["flags"] == ["stale"]
    assert box_c["eligible"] is False


def test_box_history_conformance(store):
    proc = run_cli("inventory", "--store", store, "--box", "box-a")
    assert proc.returncode == 0, proc.stderr
    lines = proc.stdout.splitlines()
    assert "3 observations" in lines[0]
    cli_rows = []
    for line in lines[1:]:
        m = re.match(r"  (\S+)\s+repo=(\S+)\s+toolset_tick=(\S+)\s+"
                     r"suspect=(\S+)", line)
        assert m, line
        cli_rows.append(m.groups())

    with api_server(store) as base:
        status, body, _ = get(base, "/fleet/boxes/box-a")
    assert status == 200
    assert body["observations"] == 3
    assert [(r["observed_at"], r["repo_commit"], r["tick"],
             "yes" if r["suspect"] else "no") for r in body["history"]] == \
        cli_rows
    # Newest-first; the deploy-first tick rule names itself.
    assert body["history"][0]["tick_source"] == "deploy"
    assert body["history"][0]["tick"] == \
        "2026-10-04T14:05:00Z-"[:19]
    assert body["data_current_as_of"] == NOW.isoformat()

    # Unknown box -> 404 with the CLI's message verbatim, as JSON.
    proc = run_cli("inventory", "--store", store, "--box", "nope")
    assert proc.returncode == 2
    assert "box nope has no records in the journal" in proc.stderr
    with api_server(store) as base:
        status, body, _ = get(base, "/fleet/boxes/nope")
    assert status == 404
    assert body["error"] == "box nope has no records in the journal"


# --- /fleet/drift ------------------------------------------------------

def test_drift_conformance(store):
    proc = run_cli("drift", "--store", store, "--expected", COMMIT_A[:12],
                   "--staleness-hours", "24")
    assert proc.returncode == 0, proc.stderr
    lines = proc.stdout.splitlines()
    cli_rows = []
    for line in lines[1:]:  # line 0 is the header
        if line.strip() == "none":
            break
        m = re.match(r"  (\S+)\s+(\(no report\)|\S+)\s+(.*)$",
                     line)
        assert m, line
        cli_rows.append(m.groups())

    with api_server(store) as base:
        status, body, _ = get(base, "/fleet/drift?expected=%s&"
                              "staleness_hours=24" % COMMIT_A[:12])
    assert status == 200
    assert [(r["box_id"], r["repo_commit"], r["reason"])
            for r in body["rows"]] == cli_rows
    assert body["expected"]["commit"] == COMMIT_A[:12]
    assert body["expected"]["commit_input"] == COMMIT_A[:12]
    assert body["expected"]["source"] == "--expected"
    assert body["commit_matching"] == \
        "12-char prefix, same as the inventory census"
    reasons = {r["box_id"]: r["reason"] for r in body["rows"]}
    assert reasons["box-b"] == "policy-held (frozen)"
    assert reasons["box-d"] == "unexplained"
    assert "box-c" not in reasons  # stale boxes excluded, like the CLI


def test_drift_majority_tie_conformance(store):
    # No --expected: a three-way tie resolves deterministically with the
    # tie wording — the API must echo the CLI's resolution verbatim.
    proc = run_cli("drift", "--store", store, "--staleness-hours", "24")
    assert proc.returncode == 0, proc.stderr
    m = re.search(r"expected (\S+) \((tie for majority \(picked \S+ "
                  r"deterministically\))\)", proc.stdout)
    assert m, proc.stdout
    cli_commit, cli_source = m.groups()

    with api_server(store) as base:
        status, body, _ = get(base, "/fleet/drift?staleness_hours=24")
    assert status == 200
    assert body["expected"]["commit"] == cli_commit
    assert body["expected"]["source"] == cli_source
    assert body["expected"]["commit_input"] == COMMIT_B  # max(winners)


# --- /fleet/events -----------------------------------------------------

def _parse_series_row(line):
    m = re.match(r"  (\S+)\s+(\d+)\s+(\S+)\s+(\S+)\s+(.*)$", line)
    assert m, line
    return m.groups()


def test_events_series_conformance(store):
    proc = run_cli("events", "--store", store, "list")
    assert proc.returncode == 0, proc.stderr
    lines = proc.stdout.splitlines()
    header_idx = next(i for i, l in enumerate(lines)
                      if re.match(r"^  box\s", l))
    cli_rows = [_parse_series_row(l) for l in lines[header_idx + 1:]
                if l.strip()]

    with api_server(store) as base:
        status, body, _ = get(base, "/fleet/events")
    assert status == 200
    assert len(body["series"]) == len(cli_rows)
    for api_row, cli_row in zip(body["series"], cli_rows):
        bid, count, outcome, emitted, note = cli_row
        assert api_row["box_id"] == bid
        assert api_row["event_count"] == int(count)
        assert api_row["last_outcome"] == outcome
        assert api_row["last_emitted_at"] == emitted
        assert api_row["last_note"] == note
    assert [s["box_id"] for s in body["series"]] == \
        [r[0] for r in cli_rows]  # same ordering
    # Histogram keys are the CLI's str(outcome) ordering; full companions.
    box_a = next(s for s in body["series"] if s["box_id"] == "box-a")
    assert box_a["outcome_histogram"] == {"succeeded": 3}
    assert box_a["last_outcome_full"] == "succeeded"
    assert box_a["last_emitted_at_full"] == \
        (NOW - timedelta(minutes=10)).isoformat()
    assert box_a["last_note_full"] == "future claim"
    assert "\x1b" not in json.dumps(body)  # evil note stripped


def test_events_box_rows_conformance(store):
    proc = run_cli("events", "--store", store, "list", "--box", "box-a")
    assert proc.returncode == 0, proc.stderr
    lines = proc.stdout.splitlines()
    assert "3 events" in lines[0]
    assert len(lines) == 2 + 3  # title + header + 3 rows

    with api_server(store) as base:
        status, body, _ = get(base, "/fleet/events?box=box-a")
    assert status == 200
    assert body["event_count"] == 3
    assert [e["event_id"] for e in body["events"]] == ["e1", "e2", "e3"]
    # Full canonical records: every journal field travels.
    e1 = body["events"][0]
    assert e1["component"] == "repo"
    assert e1["rollout"] is None
    assert e1["attested"] is False
    # The box-controlled note is stripped (the CLI renders [:60] of the
    # cleaned note; the API carries the cleaned full note — control
    # bytes die, the printable "[31m" remnants are inert text).
    assert e1["note"] == "deployed[31mred[0mforged line"
    assert lines[2].endswith(e1["note"][:60])

    # Unknown box -> 404 with the CLI's message verbatim, as JSON.
    proc = run_cli("events", "--store", store, "list", "--box", "nope")
    assert proc.returncode == 2
    with api_server(store) as base:
        status, body, _ = get(base, "/fleet/events?box=nope")
    assert status == 404
    assert body["error"] == "box nope has no events in the journal"


def test_events_wave_filter_honest(store):
    # Rollout envelopes are all null: the filter is unsatisfiable, so the
    # API answers the empty shape plus the named reason — never the full
    # journal (fail-dangerous for the S2 console).
    with api_server(store) as base:
        status, body, _ = get(base, "/fleet/events?wave=wave-1")
    assert status == 200
    # The spec-exact empty summary key-set: emptied row/summary keys,
    # not a generic shape.
    assert body["event_count"] == 0
    assert body["box_count"] == 0
    assert body["series"] == []
    assert "events" not in body
    assert body["wave_filter"] == \
        "unavailable until G15 S2 (rollout envelope null)"
    # The wave+box shape is the emptied row key-set.
    with api_server(store) as base:
        status, body, _ = get(base, "/fleet/events?wave=wave-1&box=box-a")
    assert status == 200
    assert body["box_id"] == "box-a"
    assert body["event_count"] == 0
    assert body["events"] == []
    assert body["wave_filter"] == \
        "unavailable until G15 S2 (rollout envelope null)"


# --- /fleet/alerts -----------------------------------------------------

def test_alerts_conformance(store):
    proc = run_cli("events", "--store", store, "watch")
    assert proc.returncode == 1  # pending alerts -> exit 1
    blocks = proc.stdout.split("      alert_id=")
    assert len(blocks) == 2  # one pending alert block
    head = blocks[0]
    m = re.search(r"\[([^\]]+)\] box=(\S+) subcomponent=(\S+) to=(\S+) "
                  r"fired=(\S+)", head)
    assert m, head
    rule, box_id, sub, to, fired = m.groups()
    detail_line = [l for l in head.splitlines()
                   if l.startswith("      ") and "alert_id" not in l][0]

    with api_server(store) as base:
        status, body, _ = get(base, "/fleet/alerts")
    assert status == 200
    assert body["status"] == "pending"  # <=> the CLI would exit 1
    assert body["pending_count"] == 1
    pending = [a for a in body["alerts"] if not a.get("acked")]
    assert len(pending) == 1
    alert = pending[0]
    assert alert["rule"] == rule
    assert alert["box_id"] == box_id
    assert alert["subcomponent"] == sub
    assert alert["to"][:12] == to
    assert (alert["fired_at"] or "?")[:19] == fired
    assert alert["detail"] == detail_line.strip()
    # Box-controlled detail is control-char stripped (spec §5).
    assert alert["detail"] == "box saidbad[2Kthings"
    assert alert["alert_id"] == "alert-1"
    # The acked alert rides after the pending ones (outside the CLI
    # baseline — the CLI omits acked alerts entirely).
    assert body["alerts"][-1]["alert_id"] == "alert-2"
    assert body["alerts"][-1]["acked"] is True


def test_alerts_clear_shape(store):
    os.remove(os.path.join(store, "alerts.jsonl"))
    proc = run_cli("events", "--store", store, "watch")
    assert proc.returncode == 0
    with api_server(store) as base:
        status, body, _ = get(base, "/fleet/alerts")
    assert status == 200
    assert body["status"] == "clear"
    assert body["pending_count"] == 0
    assert body["alerts"] == []


# --- /fleet/crosscheck -------------------------------------------------

def test_crosscheck_conformance(store):
    proc = run_cli("events", "--store", store, "crosscheck")
    assert proc.returncode == 1  # the e5 violation -> exit 1
    m = re.search(r"summary: (\d+) checked — (\d+) confirmed, "
                  r"(\d+) violation\(s\), (\d+) inconclusive", proc.stdout)
    assert m, proc.stdout
    total, conf, viol, incon = map(int, m.groups())

    with api_server(store) as base:
        status, body, _ = get(base, "/fleet/crosscheck")
    assert status == 200
    assert body["status"] == "violations"  # <=> the CLI would exit 1
    assert body["checked"] == total == 4  # e1, e2, e3, e5 (e4 failed: no claim)
    assert body["confirmed"] == conf == 2  # e1, e2
    assert body["violations"] == viol == 1  # e5
    assert body["inconclusive"] == incon == 1  # e3
    by_id = {v["event_id"]: v for v in body["verdicts"]}
    assert by_id["e1"]["verdict"] == "confirmed"
    assert by_id["e2"]["verdict"] == "confirmed"
    assert by_id["e5"]["verdict"] == "violation"
    assert by_id["e3"]["verdict"] == "inconclusive"
    # CLI field names and ordering preserved; display truncations match
    # the rendered row; full companions travel too.
    v5 = by_id["e5"]
    assert v5["claim_to"] == COMMIT_F[:12]
    assert v5["claim_to_full"] == COMMIT_F
    assert v5["received_at"] == \
        (NOW - timedelta(hours=2, minutes=-30)).isoformat()[:19]
    assert v5["detail"] == v5["detail_full"][:100]
    assert "flagged, not convicted" in v5["detail_full"]
    # Verdict ordering matches the CLI's (box_id, received_at) sort.
    assert [v["event_id"] for v in body["verdicts"]] == \
        ["e1", "e2", "e3", "e5"]


def test_crosscheck_no_violations_shape(store):
    os.remove(os.path.join(store, "events.jsonl"))
    with open(os.path.join(store, "events.jsonl"), "w") as fh:
        fh.write("")
    with api_server(store) as base:
        status, body, _ = get(base, "/fleet/crosscheck")
    assert status == 200
    assert body["status"] == "no-violations"
    assert body["verdicts"] == []
    assert "no checkable claims" in body["note"]


# --- /fleet/waves ------------------------------------------------------

def test_waves_reserved(store):
    with api_server(store) as base:
        status, body, _ = get(base, "/fleet/waves")
    assert status == 200
    assert body["waves"] == []
    assert body["wave_assignments"] == \
        ("unavailable until G15 S2 (rollout envelope null on all "
         "journaled events)")


# --- errors, freshness, posture ----------------------------------------

def test_missing_store_is_404(store):
    missing = os.path.join(store, "no-such-store")
    with api_server(missing) as base:
        for path in ("/fleet/boxes", "/fleet/drift", "/fleet/events",
                     "/fleet/alerts", "/fleet/crosscheck",
                     "/fleet/boxes/box-a"):
            status, body, _ = get(base, path)
            assert status == 404, path
            assert "store directory" in body["error"]
            assert "not found" in body["error"]


def test_bad_requests(store):
    with api_server(store) as base:
        status, body, _ = get(base, "/fleet/boxes?staleness_hours=abc")
        assert status == 400
        assert "staleness_hours" in body["error"]
        status, body, _ = get(base, "/fleet/boxes?staleness_hours=-1")
        assert status == 400
        status, body, _ = get(base, "/nope")
        assert status == 404
        assert body["error"] == "unknown endpoint"
        status, raw = post(base, "/fleet/alerts")
        assert status == 405
        assert json.loads(raw)["error"].startswith("method not allowed")
        # The rest of the verb surface gets the same JSON 405, not
        # stdlib's HTML 501. (HEAD carries no body per HTTP semantics —
        # assert the status and the JSON content type.)
        for method in ("OPTIONS", "TRACE", "CONNECT"):
            status, raw = raw_method(base, "/fleet/boxes", method)
            assert status == 405, method
            assert json.loads(raw)["error"].startswith(
                "method not allowed"), method
        req = urllib.request.Request(base + "/fleet/boxes", method="HEAD")
        try:
            urllib.request.urlopen(req)
            raise AssertionError("HEAD unexpectedly succeeded")
        except urllib.error.HTTPError as exc:
            assert exc.code == 405
            assert exc.headers.get("Content-Type") == "application/json"


def test_freshness_rules(store):
    with api_server(store) as base:
        _, boxes, _ = get(base, "/fleet/boxes")
        _, drift, _ = get(base, "/fleet/drift")
        _, events, _ = get(base, "/fleet/events")
        _, alerts, _ = get(base, "/fleet/alerts")
        _, cross, _ = get(base, "/fleet/crosscheck")
        _, hist, _ = get(base, "/fleet/boxes/box-a")
    # Snapshot-sourced endpoints use the snapshot's generated_at.
    assert boxes["data_current_as_of"] == boxes["snapshot_generated_at"]
    assert drift["data_current_as_of"] == drift["snapshot_generated_at"]
    assert boxes["data_current_as_of"] is not None
    # Box history uses the newest observed_at across the served records.
    assert hist["data_current_as_of"] == NOW.isoformat()
    # Event/alert endpoints use the newest received_at across journals.
    newest = (NOW + timedelta(hours=1)).isoformat()
    assert events["data_current_as_of"] == newest
    assert alerts["data_current_as_of"] == newest
    assert cross["data_current_as_of"] == newest


def test_empty_store_is_honest(store):
    for name in ("journal.jsonl", "snapshot.json", "events.jsonl",
                 "alerts.jsonl"):
        os.remove(os.path.join(store, name))
    with api_server(store) as base:
        status, body, _ = get(base, "/fleet/events")
        assert status == 200
        assert body["series"] == []
        assert body["note"] == "no journaled records; run collect first"
        status, body, _ = get(base, "/fleet/alerts")
        assert status == 200
        assert body["status"] == "clear"
        assert body["alerts"] == []
        assert body["note"] == "no journaled records; run collect first"
        # Missing snapshot is a 404, not a clean-fleet fiction.
        status, body, _ = get(base, "/fleet/boxes")
        assert status == 404
        assert "run collect first" in body["error"]


def test_box_history_journal_fallback_when_snapshot_missing(store):
    # The documented deliberate divergence: /fleet/boxes/<id> answers
    # from the journal even when the snapshot is missing, where the CLI
    # errors on the snapshot first — the API is more honest here.
    os.remove(os.path.join(store, "snapshot.json"))
    proc = run_cli("inventory", "--store", store, "--box", "box-a")
    assert proc.returncode == 2          # CLI errors on the snapshot first
    assert "no snapshot at" in proc.stderr
    with api_server(store) as base:
        status, body, _ = get(base, "/fleet/boxes/box-a")
        assert status == 200
        assert body["observations"] == 3
        assert body["data_current_as_of"] == NOW.isoformat()
        assert [r["repo_commit"] for r in body["history"]] == \
            [COMMIT_A[:12]] * 3
        # ...but the snapshot-sourced endpoints still 404 honestly.
        status, body, _ = get(base, "/fleet/boxes")
        assert status == 404
        assert "run collect first" in body["error"]


def test_unlisted_verbs_return_json(store):
    # Every response the API speaks is JSON — unlisted verbs get
    # stdlib's 501 routed through the JSON send_error override,
    # never the default HTML error page.
    with api_server(store) as base:
        for method in ("PROPFIND", "FOO"):
            req = urllib.request.Request(base + "/fleet/boxes",
                                         method=method)
            try:
                with urllib.request.urlopen(req):
                    raise AssertionError(
                        "expected HTTPError for %s" % method)
            except urllib.error.HTTPError as exc:
                assert exc.code == 501, (method, exc.code)
                assert exc.headers.get("Content-Type") == \
                    "application/json", method
                assert "error" in json.loads(
                    exc.read().decode("utf-8")), method


def test_binds_localhost_only_and_no_bind_flag(store):
    # Spec §5: binds 127.0.0.1 hardcoded; no --bind flag may exist.
    proc = run_cli("api", "--help")
    assert proc.returncode == 0
    assert "--bind" not in proc.stdout
    api.FleetAPIHandler.store_dir = store
    server = HTTPServer(("127.0.0.1", 0), api.FleetAPIHandler)
    try:
        assert server.server_address[0] == "127.0.0.1"
    finally:
        server.server_close()
    # argparse rejects a --bind attempt outright.
    proc = run_cli("api", "--store", store, "--bind", "0.0.0.0")
    assert proc.returncode == 2


def test_responses_are_json(store):
    with api_server(store) as base:
        for path in ("/fleet/boxes", "/fleet/boxes/box-a", "/fleet/drift",
                     "/fleet/events", "/fleet/events?box=box-a",
                     "/fleet/alerts", "/fleet/crosscheck", "/fleet/waves",
                     "/nope"):
            _, _, ctype = get(base, path)
            assert ctype == "application/json", path


# --- access-log scrub ------------------------------------------------------
# The request line is client-controlled and reaches the operator's
# terminal/cron log through FleetAPIHandler.log_message. A local client
# sending raw control bytes (literal ESC, not percent-encoded) must not
# be able to inject terminal escapes or forge log lines.


def test_clean_log_line_strips_controls():
    scrub = api._clean_log_line
    # C0 escapes, newline (line-forgery), DEL, and C1 (0x9b is CSI).
    assert scrub("GET /\x1b[31mRED\x1b[0m HTTP/1.1") == \
        "GET /[31mRED[0m HTTP/1.1"
    assert scrub("one\ntwo") == "onetwo"
    assert scrub("a\x7fb") == "ab"
    assert scrub("a\x9bb") == "ab"
    # Printable text (incl. non-ASCII) survives verbatim.
    assert scrub("box-α β 200 -") == "box-α β 200 -"
    # Non-strings pass through unchanged.
    assert scrub(None) is None
    assert scrub(200) == 200


def _raw_request(port, payload):
    """Send raw bytes to the test server; return the full response."""
    sock = socket.create_connection(("127.0.0.1", port), timeout=5)
    try:
        sock.sendall(payload)
        resp = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            resp += chunk
        return resp
    finally:
        sock.close()


def test_access_log_scrubs_client_control_bytes(store, monkeypatch):
    buf = io.StringIO()
    monkeypatch.setattr(sys, "stderr", buf)
    with api_server(store) as base:
        port = int(base.rsplit(":", 1)[1])
        # Case 1: literal ESC + C1 bytes in a well-formed request line.
        resp = _raw_request(
            port,
            b"GET /fleet/boxes/\x1b[31mRED\x1b[0m\x9b0m HTTP/1.1\r\n"
            b"Host: x\r\nConnection: close\r\n\r\n")
        assert resp.split(b"\r\n", 1)[0].endswith(b"404 Not Found")
        # Case 2: a bare CR in the request target. Unlike LF (which
        # http.server's readline splits on, so it never reaches the
        # logged line), CR survives readline and the rstrip('\r\n')
        # terminator strip, landing in the logged request line — pre-fix
        # a local client could overwrite the visible log line via
        # carriage return. The 4-token line fails request parsing, so
        # the 400 also exercises the log_error -> log_message path
        # through the scrub.
        resp = _raw_request(
            port,
            b"GET /fleet/boxes/\rforged-line HTTP/1.1\r\n"
            b"Host: x\r\nConnection: close\r\n\r\n")
        assert resp.split(b"\r\n", 1)[0].endswith(b"400 Bad Request")
    logged = buf.getvalue()
    assert logged, "expected at least one access-log line"
    # No raw control bytes may reach the operator's terminal.
    assert "\x1b" not in logged
    assert "\x9b" not in logged
    assert "\r" not in logged
    # The forged text cannot survive as its own log line: every logged
    # line carries the server's own prefix (the CR was stripped, so the
    # "forged-line" text rides inside the server's own 400 line).
    for line in logged.splitlines():
        assert line.startswith("fleet-api "), line
