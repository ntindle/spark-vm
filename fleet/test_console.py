"""Tests for fleet/console.py (G21 S2 operator console, issue #795).

The console consumes the S1 read API, so these tests run the real
API handlers against a fixture store and the real ``fleet events
watch`` CLI, and pin: (a) the alert board renders pending rows exactly
like the CLI (conformance); (b) the wave board states the reserved-shape
unavailability in plain operator language first, with the API's named
reason labeled on the line below; (c) the loopback guard, exit codes,
and fetch-failure honesty.

Run from the repo root:  python3 -m pytest fleet/test_console.py -q
"""

import io
import json
import os
import subprocess
import sys
import tempfile
import threading
from contextlib import contextmanager, redirect_stdout, redirect_stderr
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

FLEET = os.path.dirname(os.path.abspath(__file__))
INVENTORY = os.path.join(FLEET, "inventory.py")
CONSOLE = os.path.join(FLEET, "console.py")
sys.path.insert(0, FLEET)
import api  # noqa: E402
import console  # noqa: E402

NOW = datetime.now(timezone.utc).replace(microsecond=0)
COMMIT_A = "a" * 40


def _alert(alert_id, rule, box_id, fired_at, detail, acked=False,
           acked_at=None, acked_by=None):
    row = {"alert_id": alert_id, "rule": rule, "box_id": box_id,
           "subcomponent": "repo", "to": COMMIT_A,
           "fired_at": fired_at.isoformat(), "detail": detail,
           "acked": acked}
    if acked:
        row["acked_at"] = (acked_at or NOW).isoformat()
        row["acked_by"] = acked_by
    return row


@pytest.fixture()
def store():
    """Fixture store with one pending and one acked alert."""
    with tempfile.TemporaryDirectory() as root:
        store_dir = os.path.join(root, "store")
        os.makedirs(store_dir)
        alerts = [
            _alert("alert-1", "rule-2-stuck", "box-a",
                   NOW - timedelta(hours=2), "stuck at old commit"),
            _alert("alert-2", "rule-1-rollback", "box-b",
                   NOW - timedelta(hours=1), "old news", acked=True,
                   acked_by="operator"),
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


def run_cli(*argv):
    return subprocess.run(
        [sys.executable, INVENTORY, *argv],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def main_capture(*argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = console.main(list(argv))
    return code, buf.getvalue()


def main_capture_full(*argv):
    out_buf, err_buf = io.StringIO(), io.StringIO()
    with redirect_stdout(out_buf), redirect_stderr(err_buf):
        code = console.main(list(argv))
    return code, out_buf.getvalue(), err_buf.getvalue()


# --- alert board -------------------------------------------------------


def test_alert_board_pending_matches_cli(store):
    """Conformance: pending rows render exactly like `fleet events watch`."""
    proc = run_cli("events", "watch", "--store", store)
    assert proc.returncode == 1  # unacked alert present
    cli_lines = proc.stdout.strip().splitlines()

    status, body = api.api_alerts(store)
    assert status == 200
    board = console.render_alert_board(status, body)
    text = "\n".join(board)

    # The board's pending section is the CLI's output, line for line.
    pending = body["alerts"]
    pending = [a for a in pending if not a.get("acked")]
    start = board.index("UNACKNOWLEDGED ALERTS (%d):" % len(pending))
    for offset, cli_line in enumerate(cli_lines[1:], start=1):
        assert board[start + offset] == cli_line
    # ...and nothing else leaks into the pending section.
    assert text.index("ALREADY ACKNOWLEDGED:") > \
        text.index(cli_lines[-1])


def test_alert_board_pending_order_matches_cli():
    """The console inherits the API's fired_at-ascending ordering; the
    CLI sorts the same way — pin it with two pending alerts written
    newest-first."""
    with tempfile.TemporaryDirectory() as root:
        store_dir = os.path.join(root, "store")
        os.makedirs(store_dir)
        alerts = [
            _alert("alert-new", "rule-2-stuck", "box-a",
                   NOW - timedelta(hours=1), "newer"),
            _alert("alert-old", "rule-1-rollback", "box-b",
                   NOW - timedelta(hours=2), "older"),
        ]
        with open(os.path.join(store_dir, "alerts.jsonl"), "w") as fh:
            for alert in alerts:
                fh.write(json.dumps(alert) + "\n")
        proc = run_cli("events", "watch", "--store", store_dir)
        assert proc.returncode == 1
        cli_lines = proc.stdout.strip().splitlines()
        status, body = api.api_alerts(store_dir)
        assert status == 200
        board = console.render_alert_board(status, body)
        start = board.index("UNACKNOWLEDGED ALERTS (2):")
        for offset, cli_line in enumerate(cli_lines[1:], start=1):
            assert board[start + offset] == cli_line
        # Oldest first on both surfaces.
        assert "alert-old" in board[start + 3]
        assert "alert-new" in board[start + 6]


def test_alert_board_marks_acked_tail(store):
    status, body = api.api_alerts(store)
    lines = console.render_alert_board(status, body)
    text = "\n".join(lines)
    assert "ALREADY ACKNOWLEDGED:" in text
    # The acked alert is NOT counted in the pending header.
    assert "ALERTS: pending — 1 pending, 1 acked" in text
    # Ack provenance travels with the tail row, with the same
    # box/subcomponent/to columns as the pending rows.
    assert "by=operator" in text
    assert "subcomponent=repo" in text.split("ALREADY ACKNOWLEDGED:")[1]


def test_alert_board_empty_store():
    with tempfile.TemporaryDirectory() as store_dir:
        status, body = api.api_alerts(store_dir)
        assert status == 200
        text = "\n".join(console.render_alert_board(status, body))
        assert "ALERTS: clear — 0 pending, 0 acked" in text
        assert "no unacknowledged alerts" in text


def test_alert_board_refuses_over_cap_honestly():
    body = {"error": "alert journal over the 50000-row response bound",
            "hint": "prune the alert journal with the retention policy"}
    lines = console.render_alert_board(413, body)
    text = "\n".join(lines)
    assert text.startswith("ALERTS: API error (413)")
    assert "50000-row response bound" in text
    assert "hint: prune the alert journal" in text
    # No rows rendered past the refusal.
    assert "UNACKNOWLEDGED ALERTS" not in text


def test_alert_board_missing_store():
    status, body = api.api_alerts("/nonexistent/store")
    lines = console.render_alert_board(status, body)
    assert lines[0].startswith("ALERTS: API error (404)")


def test_alert_board_unexpected_shape():
    lines = console.render_alert_board(200, {"alerts": None})
    assert lines == ["ALERTS: unexpected response shape from the API"]
    lines = console.render_alert_board(200, ["not", "a", "dict"])
    assert lines == ["ALERTS: unexpected response shape from the API"]


# --- wave board --------------------------------------------------------


def test_wave_board_names_unavailability_plainly():
    """Fail-safe: the reserved shape is reported in operator language
    first, with the API's own named reason below — never an empty list
    that reads as "no waves"."""
    status, body = api.api_waves()
    assert status == 200
    lines = console.render_wave_board(status, body)
    assert len(lines) == 2
    assert lines[0].startswith("WAVES: wave tracking isn't available yet")
    assert "not the same as no waves" in lines[0]
    assert lines[1].strip().startswith("the API's own wording: ")
    assert body["wave_assignments"] in lines[1]


def test_wave_board_future_landed_shape():
    body = {"waves": [{"wave_id": "w1", "boxes": 3, "state": "rolling"}],
            "data_current_as_of": "2026-10-09T12:00:00Z"}
    lines = console.render_wave_board(200, body)
    assert lines[0] == "WAVES (1):"
    assert "w1" in lines[1] and "rolling" in lines[1]
    assert "fleet data current as of 2026-10-09T12:00:00Z" in lines[-1]


def test_wave_board_fetch_error():
    lines = console.render_wave_board(500, {"error": "journal unreadable"})
    assert lines == ["WAVES: API error (500) — journal unreadable"]


def test_wave_board_unexpected_shape():
    lines = console.render_wave_board(200, {"waves": None})
    assert lines == ["WAVES: unexpected response shape from the API"]
    lines = console.render_wave_board(200, "not a dict")
    assert lines == ["WAVES: unexpected response shape from the API"]


# --- fetch / transport -------------------------------------------------


class _StubHandler(BaseHTTPRequestHandler):
    """Serves one canned response for wire-level fetch_json tests."""
    response = (500, b"", "text/plain")

    def do_GET(self):
        status, payload, content_type = self.response
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


@contextmanager
def stub_api(status, payload, content_type="application/json"):
    _StubHandler.response = (status, payload, content_type)
    server = HTTPServer(("127.0.0.1", 0), _StubHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield "http://127.0.0.1:%d" % server.server_address[1]
    finally:
        server.shutdown()
        thread.join()


def test_fetch_json_error_body_over_the_wire():
    """The API's own 413 arrives as an HTTPError with a JSON body."""
    payload = json.dumps({
        "error": "alert journal over the 50000-row response bound",
        "hint": "prune the alert journal"}).encode()
    with stub_api(413, payload) as base:
        status, body = console.fetch_json(base, "/fleet/alerts", 5)
    assert status == 413
    assert body["error"].startswith("alert journal over")
    assert "hint" in body


def test_fetch_json_non_json_error_is_scrubbed():
    """A non-JSON error body (proxy page, garbage) is scrubbed and
    truncated before the operator's terminal ever sees it."""
    payload = (b"<html>oops\x00\x1b[2K" + b"x" * 500 + b"</html>")
    with stub_api(500, payload, "text/html") as base:
        status, body = console.fetch_json(base, "/fleet/alerts", 5)
    assert status == 500
    assert set(body) == {"error"}
    assert "\x00" not in body["error"]
    assert "\x1b" not in body["error"]
    assert len(body["error"]) <= 200


def test_fetch_ignores_proxy_env(monkeypatch):
    """The loopback fetch must not route through a configured proxy —
    even when no_proxy would not save it."""
    monkeypatch.setenv("http_proxy", "http://127.0.0.1:9/")
    monkeypatch.setenv("https_proxy", "http://127.0.0.1:9/")
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9/")
    monkeypatch.setenv("no_proxy", "")
    monkeypatch.setenv("NO_PROXY", "")
    with stub_api(200, b'{"ok": true}') as base:
        status, body = console.fetch_json(base, "/fleet/alerts", 5)
    assert status == 200
    assert body == {"ok": True}


def test_fetch_error_board_renders_honestly():
    boards = {"alerts": console.FetchError("cannot reach the fleet API"),
              "waves": (200, {"waves": [],
                              "wave_assignments": "unavailable until G15 S2"})}
    screen = console.render_screen("http://127.0.0.1:18760", boards)
    assert "ALERTS: cannot reach the fleet API" in screen
    assert "unavailable until G15 S2" in screen


def test_console_against_live_api(store):
    """End to end: the real console binary against the real API server."""
    with api_server(store) as base:
        proc = subprocess.run(
            [sys.executable, CONSOLE, "--api", base],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        assert proc.returncode == 1  # pending alert pages
        assert "fleet console — %s" % base in proc.stdout
        assert "UNACKNOWLEDGED ALERTS (1):" in proc.stdout
        assert "[rule-2-stuck] box=box-a" in proc.stdout
        assert "unavailable until G15 S2" in proc.stdout


# --- loopback guard ----------------------------------------------------


@pytest.mark.parametrize("host", ["127.0.0.1", "127.0.0.2", "localhost",
                                  "[::1]"])
def test_loopback_hosts_allowed(host):
    assert console.api_host_is_loopback("http://%s:18760" % host)


@pytest.mark.parametrize("host", ["192.168.1.10", "10.0.0.5", "example.com",
                                  "sparkvm.example.net", ""])
def test_non_loopback_hosts_rejected(host):
    assert not console.api_host_is_loopback("http://%s:18760" % host)


def test_main_rejects_remote_api():
    """The guard must be enforced in main(), not just exist as a
    predicate: assert the stderr refusal and that nothing renders."""
    code, out, err = main_capture_full("--api", "http://192.168.1.10:18760")
    assert code == 64
    assert "must be a loopback host" in err
    assert out == ""  # refused before any fetch or render


def test_main_rejects_bad_timeout():
    code, out, err = main_capture_full("--timeout", "0")
    assert code == 64
    assert "must be a positive finite number of seconds" in err
    assert out == ""


def test_watch_nonfinite_interval_is_usage_error():
    # ("-inf" is rejected by argparse itself as a flag-like token, before
    # our code runs — also a clean usage error, just not ours to test.)
    for bad in ("nan", "inf"):
        code, out, err = main_capture_full("--watch", bad)
        assert code == 64, bad
        assert "positive finite interval" in err, bad
        assert "Traceback" not in err, bad
        assert out == "", bad


def test_timeout_nonfinite_is_usage_error():
    for bad in ("nan", "inf"):
        code, out, err = main_capture_full("--timeout", bad)
        assert code == 64, bad
        assert "Traceback" not in err, bad
        assert out == "", bad


def test_alert_board_rejects_non_dict_rows():
    lines = console.render_alert_board(200, {"alerts": [123]})
    assert lines == ["ALERTS: unexpected response shape from the API"]


# --- exit codes --------------------------------------------------------


def test_once_exit_1_on_pending(store):
    with api_server(store) as base:
        code, _ = main_capture("--api", base)
        assert code == 1


def test_once_exit_0_when_clear():
    with tempfile.TemporaryDirectory() as root:
        store_dir = os.path.join(root, "store")
        os.makedirs(store_dir)
        with open(os.path.join(store_dir, "alerts.jsonl"), "w") as fh:
            fh.write(json.dumps(_alert(
                "a1", "rule-1", "box-a", NOW, "done", acked=True)) + "\n")
        with api_server(store_dir) as base:
            code, out = main_capture("--api", base)
            assert code == 0
            assert "no unacknowledged alerts" in out


def test_once_exit_2_on_unreachable_api():
    # Ephemeral port with nothing listening: connection refused.
    code, out = main_capture("--api", "http://127.0.0.1:1", "--timeout", "2")
    assert code == 2
    assert "ALERTS: cannot reach the fleet API" in out


def test_board_waves_subset():
    with tempfile.TemporaryDirectory() as store_dir:
        with api_server(store_dir) as base:
            _, out = main_capture("--api", base, "--board", "waves")
            assert "WAVES:" in out
            assert "ALERTS:" not in out


def test_board_alerts_subset(store):
    with api_server(store) as base:
        code, out = main_capture("--api", base, "--board", "alerts")
        assert code == 1  # pending alert still pages
        assert "ALERTS:" in out
        assert "WAVES:" not in out


def test_watch_negative_interval_is_usage_error():
    # A usage error must never dump a traceback in an operator tool.
    code, out, err = main_capture_full("--watch", "-5")
    assert code == 64
    assert "--watch needs a positive finite interval" in err
    assert "Traceback" not in err
    assert out == ""


def test_watch_zero_is_usage_error_not_silent_once():
    # --watch 0 must fail loudly (exit 64): silently degrading to the
    # one-shot path is a fail-dangerous misread of the operator's intent.
    code, out, err = main_capture_full("--watch", "0")
    assert code == 64
    assert "--watch needs a positive finite interval" in err
    assert "Traceback" not in err
    assert out == ""


def test_watch_negative_zero_float_is_usage_error():
    # --watch -0.0 is the float edge of the non-positive gate: argparse
    # hands run_watch a float, and the explicit-value contract (exit 64,
    # not a silent one-shot) must hold for -0.0 exactly as for 0 and -5.
    code, out, err = main_capture_full("--watch", "-0.0")
    assert code == 64
    assert "--watch needs a positive finite interval" in err
    assert "Traceback" not in err
    assert out == ""


def test_once_with_watch_zero_is_usage_error():
    # An explicit --watch 0 is a usage error even when --once is also
    # given: the flag's presence is contractual, not the mode. (The
    # 2026-10-09 explicit-zero hardening — old code silently ran once.)
    code, out, err = main_capture_full("--once", "--watch", "0")
    assert code == 64
    assert "--watch needs a positive finite interval" in err
    assert "Traceback" not in err
    assert out == ""


def test_watch_omitted_runs_once_not_watch():
    # The default (no --watch flag) must be the one-shot path: against an
    # unreachable API it exits 2 quickly, while watch mode would loop.
    code, out = main_capture("--api", "http://127.0.0.1:1", "--timeout", "2")
    assert code == 2
    assert "ALERTS: cannot reach the fleet API" in out


def test_watch_header_proves_liveness():
    header = console.watch_header(30)
    assert "refreshing every 30s" in header
    assert "Ctrl-C" in header


def test_once_flag_is_accepted(store):
    with api_server(store) as base:
        code, out = main_capture("--api", base, "--once")
        assert code == 1
        assert "UNACKNOWLEDGED ALERTS (1):" in out
