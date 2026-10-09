#!/usr/bin/env python3
"""Tests for the #845 fleet dashboard.

- byte-identity: the control-plane worker.py inlines dashboard.html
  (single-file deploy); the copies must match byte-for-byte. The worker
  path resolves as SPARKVM_WORKER_PATH (env) or the loop VM's
  control-plane checkout default — set the env to point the test at a
  real worker instead of relying on the skip. Skipped only when no
  worker source is reachable (e.g. CI on a fork).
- sync: sync_dashboard.py mechanically rewrites the inlined block; the
  sync tests pin its contract (idempotent, --check detects drift,
  refusals are loud).
- static: the page carries the required views/ids, keeps the owner key
  out of localStorage/URLs, and contains no '\"\"\"' (it would break the
  inlined Python string in worker.py).
- js: the page's script passes `node --check`, and the pure helpers
  (esc/relTime/until/isStale/fmtUptime/statusChip/shortId) plus the pure
  row renderers (fleetRow/pairingCard/detailRows/serviceChips) are
  unit-tested in node by extracting the helper block and stubbing the
  browser globals they touch. #859: the XSS tests call the REAL
  templates with hostile box-controlled inputs — a template that drops
  an esc() must fail them (pinned by test_xss_tests_catch_a_dropped_esc).
"""
import json
import os
import re
import subprocess
import tempfile

import pytest

from sync_dashboard import BEGIN, END, SyncError, resolve_worker_path
import sync_dashboard

HERE = os.path.dirname(os.path.abspath(__file__))
HTML_PATH = os.path.join(HERE, "dashboard.html")
WORKER_PATH = resolve_worker_path()

_SKIP_MSG = ("worker source not reachable here "
             "(set SPARKVM_WORKER_PATH to run this test)")


def _html():
    with open(HTML_PATH, encoding="utf-8") as f:
        return f.read()


# --- byte-identity -----------------------------------------------------

def _inline_html(worker_path=WORKER_PATH):
    src = open(worker_path, encoding="utf-8").read()
    assert BEGIN in src, "dashboard block missing from worker.py"
    block = src.split(BEGIN)[1].split(END)[0]
    # Block shape: comment lines, then DASHBOARD_HTML = """<html>"""
    m = re.search(r'DASHBOARD_HTML = """(.*)"""\s*$', block, re.S)
    assert m, "DASHBOARD_HTML string not found in dashboard block"
    return m.group(1)


def test_worker_inline_copy_byte_identical():
    if not os.path.exists(WORKER_PATH):
        pytest.skip(_SKIP_MSG)
    assert _inline_html() == _html(), \
        "worker.py's inlined dashboard.html has drifted"


def test_fleet_rows_keyboard_accessible():
    html = _html()
    assert 'tabindex="0"' in html and 'role="button"' in html


def test_worker_serves_dashboard_at_root():
    if not os.path.exists(WORKER_PATH):
        pytest.skip(_SKIP_MSG)
    src = open(WORKER_PATH, encoding="utf-8").read()
    assert 'path == "/" and method == "GET"' in src
    assert '"Content-Type": "text/html' in src
    assert '"X-Content-Type-Options": "nosniff"' in src
    assert '"X-Frame-Options": "DENY"' in src


# --- sync --------------------------------------------------------------

import sys as _sys

_THIS = _sys.modules[__name__]


def _scratch_worker(path, html=None):
    """Write a minimal worker.py with a canonical dashboard block."""
    html = _html() if html is None else html
    with open(path, "w", encoding="utf-8") as f:
        f.write("#!/usr/bin/env python3\n# synthetic worker\n")
        f.write(sync_dashboard.BEGIN + "\n")
        f.write("\n".join(sync_dashboard.HEADER_LINES) + "\n")
        f.write('DASHBOARD_HTML = """' + html + '"""\n')
        f.write(sync_dashboard.END + "\n")
        f.write("SENTINEL = 1\n")
    return path


def test_resolve_worker_path_honors_env(monkeypatch):
    monkeypatch.setenv("SPARKVM_WORKER_PATH", "/tmp/some-worker.py")
    assert resolve_worker_path() == "/tmp/some-worker.py"
    monkeypatch.delenv("SPARKVM_WORKER_PATH", raising=False)
    assert resolve_worker_path() == sync_dashboard.DEFAULT_WORKER_PATH


def test_sync_is_idempotent(tmp_path):
    w = _scratch_worker(str(tmp_path / "worker.py"))
    assert sync_dashboard.sync(w) is True  # already canonical
    before = open(w, encoding="utf-8").read()
    assert sync_dashboard.sync(w) is True
    assert open(w, encoding="utf-8").read() == before


def test_sync_check_detects_drift_without_writing(tmp_path):
    w = _scratch_worker(str(tmp_path / "worker.py"),
                        html="<!-- stale copy -->\n" + _html())
    before = open(w, encoding="utf-8").read()
    assert sync_dashboard.sync(w, check=True) is False
    assert open(w, encoding="utf-8").read() == before  # --check wrote nothing
    assert sync_dashboard.sync(w) is False  # rewrote
    assert sync_dashboard.sync(w, check=True) is True
    assert _inline_html(w) == _html()


def test_main_check_exit_codes(tmp_path):
    in_sync = _scratch_worker(str(tmp_path / "worker.py"))
    drifted = _scratch_worker(str(tmp_path / "drifted.py"),
                              html="<!-- stale copy -->\n" + _html())
    # In sync: --check exits 0. Drifted: --check exits 1 and writes
    # nothing; a plain run repairs it and exits 0.
    assert sync_dashboard.main(["--worker", in_sync, "--check"]) == 0
    before = open(drifted, encoding="utf-8").read()
    assert sync_dashboard.main(["--worker", drifted, "--check"]) == 1
    assert open(drifted, encoding="utf-8").read() == before
    assert sync_dashboard.main(["--worker", drifted]) == 0
    assert sync_dashboard.main(["--worker", drifted, "--check"]) == 0
    assert _inline_html(drifted) == _html()


def test_main_refusals_exit_2(tmp_path):
    # Missing markers and an unreadable worker are both SyncError — both
    # must exit 2, never a traceback exit code.
    no_markers = str(tmp_path / "worker.py")
    with open(no_markers, "w", encoding="utf-8") as f:
        f.write("# no markers here\n")
    assert sync_dashboard.main(["--worker", no_markers]) == 2
    assert sync_dashboard.main(
        ["--worker", str(tmp_path / "does-not-exist.py")]) == 2
    assert open(no_markers, encoding="utf-8").read() == "# no markers here\n"


def test_byte_identity_fails_when_html_drifts(tmp_path, monkeypatch):
    # Acceptance pin for #858: with a worker reachable, an edit to
    # dashboard.html that skips the re-inline must fail the assertion.
    canonical = _html()
    w = _scratch_worker(str(tmp_path / "worker.py"))
    assert _inline_html(w) == canonical  # control: in sync before the edit
    mutated = str(tmp_path / "mutated.html")
    with open(mutated, "w", encoding="utf-8") as f:
        f.write(canonical + "\n<!-- un-synced edit -->\n")
    monkeypatch.setattr(_THIS, "HTML_PATH", mutated)
    with pytest.raises(AssertionError):
        assert _inline_html(w) == _html()
    # And the sync path restores it.
    monkeypatch.undo()
    stale = _scratch_worker(str(tmp_path / "worker2.py"),
                            html="<!-- stale copy -->\n" + canonical)
    assert sync_dashboard.sync(stale) is False  # rewrote
    assert _inline_html(stale) == canonical


def test_sync_refuses_missing_markers(tmp_path):
    w = str(tmp_path / "worker.py")
    with open(w, "w", encoding="utf-8") as f:
        f.write("# no markers here\n")
    with pytest.raises(SyncError):
        sync_dashboard.sync(w)
    assert open(w, encoding="utf-8").read() == "# no markers here\n"


def test_sync_refuses_duplicated_markers(tmp_path):
    w = _scratch_worker(str(tmp_path / "worker.py"))
    with open(w, "a", encoding="utf-8") as f:
        f.write(sync_dashboard.BEGIN + "\n")
    with pytest.raises(SyncError):
        sync_dashboard.sync(w)


def test_sync_refuses_odd_trailing_backslash(tmp_path, monkeypatch):
    # An odd trailing backslash escapes the closing """ of the inlined
    # string — the worker would come out syntactically broken.
    bad = str(tmp_path / "bad.html")
    with open(bad, "w", encoding="utf-8") as f:
        f.write("<!DOCTYPE html>\n<p>x</p>\\")
    monkeypatch.setattr(sync_dashboard, "HTML_PATH", bad)
    w = _scratch_worker(str(tmp_path / "worker.py"))
    with pytest.raises(SyncError, match="backslashes"):
        sync_dashboard.sync(w)
    # The worker is untouched — the refusal happened before any write.
    assert _inline_html(w) == _html()


def test_sync_accepts_even_trailing_backslashes(tmp_path, monkeypatch):
    # Escaped pairs can't touch the closing quotes — safe to inline.
    ok = str(tmp_path / "ok.html")
    with open(ok, "w", encoding="utf-8") as f:
        f.write("<!DOCTYPE html>\n<p>x</p>\\\\")
    monkeypatch.setattr(sync_dashboard, "HTML_PATH", ok)
    w = _scratch_worker(str(tmp_path / "worker.py"))
    assert sync_dashboard.sync(w) is False  # rewrote
    assert _inline_html(w).endswith("\\\\")


def test_sync_refuses_begin_on_last_line(tmp_path):
    # BEGIN on the final line with no newline after it: the old code died
    # with a bare ValueError from str.index instead of a loud SyncError.
    w = str(tmp_path / "worker.py")
    with open(w, "w", encoding="utf-8") as f:
        f.write("#!/usr/bin/env python3\n" + sync_dashboard.END + "\n"
                + sync_dashboard.BEGIN)
    with pytest.raises(SyncError, match="last line"):
        sync_dashboard.sync(w)


def test_sync_preserves_end_marker_indentation(tmp_path):
    # The END marker line is kept byte-for-byte (indentation included),
    # symmetric with the BEGIN side — an indented END used to be silently
    # dedented by the rewrite.
    w = str(tmp_path / "worker.py")
    with open(w, "w", encoding="utf-8") as f:
        f.write("#!/usr/bin/env python3\n")
        f.write(sync_dashboard.BEGIN + "\n")
        f.write("\n".join(sync_dashboard.HEADER_LINES) + "\n")
        f.write('DASHBOARD_HTML = """' + _html() + '"""\n')
        f.write("    " + sync_dashboard.END + "\n")
        f.write("SENTINEL = 1\n")
    before = open(w, encoding="utf-8").read()
    assert sync_dashboard.sync(w) is True  # already in sync
    assert open(w, encoding="utf-8").read() == before  # nothing rewritten


def test_sync_refuses_triple_quote_html(tmp_path, monkeypatch):
    bad = str(tmp_path / "bad.html")
    with open(bad, "w", encoding="utf-8") as f:
        f.write('<!DOCTYPE html>\n""" boom """\n')
    monkeypatch.setattr(sync_dashboard, "HTML_PATH", bad)
    w = _scratch_worker(str(tmp_path / "worker.py"))
    with pytest.raises(SyncError):
        sync_dashboard.sync(w)
    # The worker is untouched — the refusal happened before any write.
    assert _inline_html(w) == _html()


# --- static ------------------------------------------------------------

def test_no_triple_quote():
    assert '"""' not in _html(), \
        '""" would terminate the inlined Python string in worker.py'


def test_required_views_and_ids():
    html = _html()
    for token in ("login-view", "app-view", "fleet-list", "detail-card",
                  "detail-approvals", "pairing-list", "key-input",
                  "login-form", "logout-btn", "refresh-btn",
                  "agent-login-view", "agent-view", "agent-login-btn",
                  "agent-logout-btn", "agent-dl"):
        assert 'id="%s"' % token in html, "missing #%s" % token


def test_agentid_config_present_but_unconfigured():
    html = _html()
    # The public OIDC client id ships in the page once registered; it
    # starts empty and the UI says so.
    assert "AGENTID" in html
    assert 'client_id: ""' in html
    assert "agent-login-unconfigured" in html


def test_no_client_secret_anywhere():
    html = _html()
    # AgentID is a PUBLIC client (PKCE, token_endpoint_auth_method
    # "none"): a client secret must never appear in this page.
    assert "client_secret" not in html.lower(), \
        "client secret material must never ship in the dashboard"


def test_owner_key_never_persisted_or_leaked():
    html = _html()
    # No *usage* of the localStorage API (the login copy may name it in the
    # "never in a cookie, localStorage, or a URL" guarantee).
    assert "localStorage." not in html, "owner key must not touch localStorage"
    assert "document.cookie" not in html, "owner key must not touch cookies"
    assert "sessionStorage" in html  # the sanctioned store
    # The password input must not retain the key after sign-in succeeds.
    assert 'getElementById("key-input").value = ""' in html
    # No key material in URLs: no query-string construction with the key.
    assert "encodeURIComponent(KEY" not in html
    assert "?key=" not in html and "&key=" not in html


def test_api_calls_are_same_origin():
    html = _html()
    for path in ('"/v1/boxes"', '"/v1/pairing"'):
        assert path in html, "dashboard must call %s relatively" % path
    # Approval list/decide URLs are built by concatenation — the path
    # fragments must stay relative, never hard-coded absolute.
    assert '"/v1/boxes/"' in html
    assert "/approvals?status=pending&limit=50" in html
    assert "/approvals/" in html and '/decision"' in html
    assert "https://api.sparkvm.dev" not in html, \
        "no hard-coded plane origin; the page calls the plane that served it"


def test_stale_threshold_documented_and_constant():
    html = _html()
    assert "STALE_AFTER_S = 300" in html


def test_login_gate_on_401():
    html = _html()
    assert "resp.status === 401" in html and "logout(true)" in html


# --- js -----------------------------------------------------------------

def _script():
    html = _html()
    m = re.search(r"<script>(.*)</script>", html, re.S)
    assert m, "no inline script found"
    return m.group(1)


def _node_eval(fragment, helpers=None):
    """Evaluate the pure-helper script plus `fragment` in node; the
    fragment must print one JSON object to stdout, which is returned
    parsed. Pass `helpers=` to evaluate a mutated helper block instead
    (mutation non-vacuity testing)."""
    if helpers is None:
        helpers = _script().split("/* ---- app state ---- */")[0]
    harness = helpers + "\n" + fragment
    with tempfile.NamedTemporaryFile("w", suffix=".js",
                                     delete=False) as f:
        f.write(harness)
        path = f.name
    try:
        r = subprocess.run(["node", path], capture_output=True, text=True,
                           timeout=30)
    finally:
        os.unlink(path)
    assert r.returncode == 0, "node harness failed:\n%s" % r.stderr
    return json.loads(r.stdout)


def test_js_syntax():
    script = _script()
    with tempfile.NamedTemporaryFile("w", suffix=".js",
                                     delete=False) as f:
        f.write(script)
        path = f.name
    try:
        r = subprocess.run(["node", "--check", path], capture_output=True,
                           text=True, timeout=30)
    finally:
        os.unlink(path)
    assert r.returncode == 0, "node --check failed:\n%s" % r.stderr


def _run_helpers():
    """Evaluate the pure helpers in node; returns parsed JSON results."""
    script = _script()
    # Helpers end at the '/* ---- app state ---- */' marker; stub the
    # browser globals the helper block references at parse time (none —
    # but `var` at top level is fine in node).
    helpers = script.split("/* ---- app state ---- */")[0]
    harness = helpers + """
const out = {
  esc: esc('<a href="x">&"\\''),
  rel1: relTime(1000, 1042),      // 42s ago
  rel2: relTime(1000, 1000 + 90), // 1m ago
  rel3: relTime(1000, 1000 + 3700),
  rel4: relTime(1000, 1000 + 90000),
  relNever: relTime(null, 1000),
  relFuture: relTime(2000, 1000), // clamps to 0s
  until1: until(1090, 1000),
  until2: until(1000 + 1500, 1000),
  untilNull: until(null, 1000),
  staleFresh: isStale(1000, 1299),   // 299s — fresh
  staleEdge: isStale(1000, 1301),    // 301s — stale
  staleNull: isStale(null, 1000),
  up1: fmtUptime(45),
  up2: fmtUptime(3700),
  up3: fmtUptime(90000),
  chipLive: statusChip({last_heartbeat_at: 1290}, 1300),
  chipStale: statusChip({last_heartbeat_at: 900}, 1300),
  chipNone: statusChip({}, 1300),
  short1: shortId("box_7dccb3daabcdef"),
  short2: shortId("box_abc"),
};
console.log(JSON.stringify(out));
"""
    with tempfile.NamedTemporaryFile("w", suffix=".js",
                                     delete=False) as f:
        f.write(harness)
        path = f.name
    try:
        r = subprocess.run(["node", path], capture_output=True, text=True,
                           timeout=30)
    finally:
        os.unlink(path)
    assert r.returncode == 0, "helper harness failed:\n%s" % r.stderr
    import json
    return json.loads(r.stdout)


def test_js_helpers():
    o = _run_helpers()
    assert o["esc"] == "&lt;a href=&quot;x&quot;&gt;&amp;&quot;&#39;"
    assert o["rel1"] == "42s ago"
    assert o["rel2"] == "1m ago"
    assert o["rel3"] == "1h ago"
    assert o["rel4"] == "1d ago"
    assert o["relNever"] == "never"
    assert o["relFuture"] == "0s ago"
    assert o["until1"] == "in 1m"
    assert o["until2"] == "in 25m"
    assert o["untilNull"] == "unknown"
    assert o["staleFresh"] is False
    assert o["staleEdge"] is True
    assert o["staleNull"] is True
    assert o["up1"] == "0m"
    assert o["up2"] == "1h 1m"
    assert o["up3"] == "1d 1h"
    assert 'class="chip ok"' in o["chipLive"] and ">Live<" in o["chipLive"]
    assert 'class="chip stale"' in o["chipStale"] and ">Stale<" in o["chipStale"]
    assert "No heartbeat" in o["chipNone"]
    assert o["short1"] == "box_7dccb3daab…"
    assert o["short2"] == "box_abc"


def test_xss_escaping_of_box_fields():
    """Box-controlled strings (name/id) must be escaped in the row HTML.

    Calls the REAL fleetRow() template (the same function renderFleet
    injects into the page) with a hostile name/id and asserts no raw
    markup survives."""
    box = {"id": 'box_1"><img src=x onerror=alert(1)>',
           "name": "<script>alert(2)</script>",
           "last_heartbeat_at": 1290}
    o = _node_eval("""
const b = %s;
console.log(JSON.stringify({row: fleetRow(b, 1300)}));
""" % json.dumps(box))
    row = o["row"]
    assert "<script>" not in row and "<img" not in row
    assert "&lt;script&gt;" in row
    # The hostile id must not break out of the data-id attribute either.
    assert 'data-id="' in row
    assert "&quot;" in row


def test_xss_escaping_of_pairing_fields():
    """Pairing rows carry box-controlled name/id/fingerprint — all must
    be escaped by the REAL pairingCard() template."""
    p = {"id": 'p_1"><img src=x onerror=alert(1)>',
         "box_name": "<script>alert(2)</script>",
         "status": "pending",
         "expires_at": 1900,
         "fingerprint": "<b>finger</b>print"}
    o = _node_eval("""
const p = %s;
console.log(JSON.stringify({
  pending: pairingCard(p, 1300),
  approved: pairingCard(Object.assign({}, p, {status: "approved"}), 1300),
}));
""" % json.dumps(p))
    for rendered in (o["pending"], o["approved"]):
        assert "<script>" not in rendered and "<img" not in rendered
        assert "&lt;script&gt;" in rendered
        assert "&lt;b&gt;" in rendered


def test_xss_escaping_of_detail_fields():
    """Box-controlled detail fields (id, status, hostname, uptime note,
    token note, services) must be escaped by the REAL detailRows() /
    serviceChips() templates."""
    box = {"id": 'box_1"><img src=x onerror=alert(1)>',
           "name": "irrelevant-here",
           "status": 'up"><svg onload=alert(3)>',
           "last_heartbeat_at": 1290,
           "created_at": 900,
           "token_expires_at": 9999999999,
           "last_status": {
               "host": {"hostname": 'h"><iframe src=x>', "uptime_seconds": 3661},
               "services": {'svc"><b>x': 'up', "svc2": 'down"><img src=x onerror=alert(4)>'},
           }}
    o = _node_eval("""
const b = %s;
console.log(JSON.stringify({
  rows: detailRows(b, 1300),
  chips: serviceChips(b.last_status.services),
  empty: serviceChips({}),
}));
""" % json.dumps(box))
    for rendered in (o["rows"], o["chips"]):
        assert "<img" not in rendered and "<svg" not in rendered
        assert "<iframe" not in rendered and "<b>" not in rendered
    assert "&lt;script&gt;" not in o["rows"]  # no script hostile here either
    assert "no service data" in o["empty"]


def test_xss_tests_catch_a_dropped_esc():
    """Non-vacuity pin for #859: the issue's acceptance criterion is
    that mutating a template to drop an esc() fails the suite. Prove
    the hostile-input assertions are sensitive — one dropped esc()
    per template must leak raw markup."""
    helpers = _script().split("/* ---- app state ---- */")[0]
    box = {"id": 'box_1"><img src=x onerror=alert(1)>',
           "name": "<script>alert(2)</script>",
           "status": 'up"><svg onload=alert(3)>',
           "last_heartbeat_at": 1290,
           "created_at": 900,
           "last_status": {"host": {"hostname": "h", "uptime_seconds": 1},
                           "services": {}}}
    cases = [
        # (needle, replacement, js expression, raw marker that must leak)
        ("esc(b.name)", "String(b.name)",
         "fleetRow(b, 1300)", "<script>"),
        ("esc(p.box_name)", "String(p.box_name)",
         "pairingCard(p, 1300)", "<script>"),
        ('esc(host.hostname || "—")', '(host.hostname || "—")',
         "detailRows(b, 1300)", 'h"><iframe src=x>'),
        ("esc(svcs[n])", "String(svcs[n])",
         "serviceChips({'svc2': 'down\"><img src=x onerror=alert(4)>'})",
         "<img"),
        ("esc(scrubCtrl(a.summary))", "String(scrubCtrl(a.summary))",
         "approvalCard(a, 1300)", "<script>"),
    ]
    p = dict(box)
    p["box_name"] = box["name"]
    p["status"] = "pending"
    p["expires_at"] = 1900
    p["fingerprint"] = "fp"
    box["last_status"]["host"]["hostname"] = 'h"><iframe src=x>'
    a = {"aid": 'a_1"><img src=x onerror=alert(9)>',
         "box_id": "box_1",
         "summary": "<script>alert(5)</scr" + "ipt>",
         "status": "pending",
         "created_at": 900,
         "expires_at": 1900}
    for needle, repl, expr, leaked in cases:
        assert helpers.count(needle) >= 1, "mutation needle vanished: %r" % needle
        mutated = helpers.replace(needle, repl, 1)  # drop ONE esc()
        o = _node_eval("""
const b = %s;
const p = %s;
const a = %s;
console.log(JSON.stringify({out: %s}));
""" % (json.dumps(box), json.dumps(p), json.dumps(a), expr), helpers=mutated)
        assert leaked in o["out"], \
            "dropped esc() in %r did not leak — the test is vacuous" % needle
    # Sanity: the same expressions on the UNMUTATED helpers escape fully.
    o = _node_eval("""
const b = %s;
console.log(JSON.stringify({out: fleetRow(b, 1300)}));
""" % json.dumps(box))
    assert "<script>" not in o["out"]


def test_approval_card_xss_and_control_neutralization():
    """#954: the approval summary is box-controlled data — the REAL
    approvalCard() template must escape markup AND neutralize control
    characters / terminal escapes."""
    a = {"aid": 'a_1"><img src=x onerror=alert(9)>',
         "box_id": "box_1",
         # hostile markup + ESC + C1 control smuggled into the summary
         "summary": '<script>alert(5)</scr' + 'ipt>\x1b[31mred\x85tail',
         "status": "pending",
         "created_at": 900,
         "expires_at": 1900}
    o = _node_eval("""
const a = %s;
console.log(JSON.stringify({
  pending: approvalCard(a, 1300),
  denied: approvalCard(Object.assign({}, a, {status: "denied",
                                             decision: "deny",
                                             decided_by: "owner_<svg>",
                                             decided_at: 1200}), 1300),
}));
""" % json.dumps(a))
    pending, denied = o["pending"], o["denied"]
    for rendered in (pending, denied):
        assert "<script>" not in rendered and "<img" not in rendered
        assert "\x1b" not in rendered and "\x85" not in rendered
        assert "&lt;script&gt;" in rendered
    # Hostile aid must not break out of the data-aid attribute.
    assert 'data-aid="' in pending
    assert "&quot;" in pending
    # Pending card has both decide buttons; decided card has none and
    # shows the terminal decision line.
    assert pending.count("decide-btn") == 2
    assert "Deny" in pending and "Approve" in pending
    assert "decide-btn" not in denied
    assert "denied" in denied and "owner_&lt;svg&gt;" in denied
    assert "in 10m" in pending  # until(1900, 1300)


def test_approval_chip_terminal_states():
    """#954 acceptance: expired reads as expired, never pending."""
    o = _node_eval("""
console.log(JSON.stringify({
  pending: approvalChip({status: "pending"}),
  approved: approvalChip({status: "approved"}),
  denied: approvalChip({status: "denied"}),
  expired: approvalChip({status: "expired"}),
}));
""")
    assert ">Pending<" in o["pending"]
    assert ">Approved<" in o["approved"]
    assert ">Denied<" in o["denied"]
    assert ">Expired<" in o["expired"]
    assert "chip stale" in o["expired"]
    assert "chip pending" not in o["expired"]


def test_scrub_ctrl_strips_c0_c1():
    o = _node_eval("""
console.log(JSON.stringify({
  clean: scrubCtrl("normal text"),
  escapes: scrubCtrl("\\x1b[31mred\\x1b[0m"),
  c1: scrubCtrl("a\\x85\\x9bb"),
  null: scrubCtrl(null),
}));
""")
    assert o["clean"] == "normal text"
    assert o["escapes"] == "[31mred[0m"  # ESC byte gone, printable leftovers
    assert o["c1"] == "ab"
    assert o["null"] == ""


# --- AgentID ------------------------------------------------------------

import base64 as _b64


def _agentid_token(payload):
    """Craft an unsigned compact JWS carrying `payload` (signature is a
    dummy — parseIdToken/validateAgentClaims are claim checks, not
    signature checks; the plane re-verifies ES256 server-side)."""
    def enc(o):
        return _b64.urlsafe_b64encode(
            json.dumps(o).encode()).rstrip(b"=").decode()
    return enc({"alg": "ES256", "typ": "JWT"}) + "." + enc(payload) + ".sig"


def _agentid_claims(**kw):
    c = {"iss": "https://auth.agentid.com", "aud": "cid-123",
         "actor_type": "agent", "nonce": "n-1", "iat": 1700,
         "exp": 1900, "owner_sub": "owner-1",
         "owner_email": "owner@example.com"}
    c.update(kw)
    return c


def _agentid_opts(**kw):
    o = {"issuer": "https://auth.agentid.com", "clientId": "cid-123",
         "nonce": "n-1", "now": 1800}
    o.update(kw)
    return o


def test_agentid_authorize_url():
    o = _node_eval("""
var url = agentidAuthorizeUrl(AGENTID, "https://plane.example/",
                              "ch-al", "st-1", "no-1");
console.log(JSON.stringify({url: url}));
""")
    u = o["url"]
    assert u.startswith("https://auth.agentid.com/v0/authorize?")
    for kv in ("response_type=code", "scope=openid%20owner_email",
               "state=st-1", "nonce=no-1", "code_challenge=ch-al",
               "code_challenge_method=S256", "client_id=",
               "redirect_uri=https%3A%2F%2Fplane.example%2F"):
        assert kv in u, "missing %r in %r" % (kv, u)
    # No secret material in the authorize redirect, ever.
    assert "secret" not in u.lower()


def test_agentid_parse_id_token():
    tok = _agentid_token(_agentid_claims())
    o = _node_eval("""
var c = parseIdToken(%s);
console.log(JSON.stringify({actor: c.actor_type, email: c.owner_email,
                            sub: c.owner_sub}));
""" % json.dumps(tok))
    assert o == {"actor": "agent", "email": "owner@example.com",
                 "sub": "owner-1"}


def test_agentid_parse_id_token_rejects_malformed():
    o = _node_eval("""
var errs = [];
["nope", "a.b", "a.b.c.d"].forEach(function (t) {
  try { parseIdToken(t); errs.push("no-throw"); }
  catch (e) { errs.push("threw"); }
});
console.log(JSON.stringify({errs: errs}));
""")
    assert o["errs"] == ["threw", "threw", "threw"]


def test_agentid_validate_claims_happy():
    o = _node_eval("""
var claims = parseIdToken(%s);
console.log(JSON.stringify({
  ok: validateAgentClaims(claims, %s),
  audArray: validateAgentClaims(
    parseIdToken(%s), %s),
}));
""" % (json.dumps(_agentid_token(_agentid_claims())),
       json.dumps(_agentid_opts()),
       json.dumps(_agentid_token(_agentid_claims(aud=["x", "cid-123"]))),
       json.dumps(_agentid_opts())))
    assert o["ok"] is None
    assert o["audArray"] is None


def test_agentid_validate_claims_rejects():
    cases = [
        ({"iss": "https://evil.example"}, {}, "unexpected issuer"),
        ({"aud": "other"}, {}, "audience mismatch"),
        ({"actor_type": "human"}, {}, "not an agent identity"),
        ({"actor_type": "user"}, {}, "not an agent identity"),
        ({}, {"nonce": "wrong"}, "nonce mismatch"),
        ({"exp": 1700}, {}, "token expired"),
        ({"iat": 1800 + 301}, {}, "token issued in the future"),
    ]
    for claim_kw, opt_kw, reason in cases:
        o = _node_eval("""
var claims = parseIdToken(%s);
console.log(JSON.stringify({
  problem: validateAgentClaims(claims, %s),
}));
""" % (json.dumps(_agentid_token(_agentid_claims(**claim_kw))),
       json.dumps(_agentid_opts(**opt_kw))))
        assert o["problem"] == reason, \
            "expected %r for %r, got %r" % (reason, claim_kw, o["problem"])


# --- app-state (DOM-stubbed node tests) ------------------------------------

_APP_PREAMBLE = """
function __makeEl() {
  var el = {
    textContent: "", innerHTML: "", value: "", disabled: false,
    _cls: {}, listeners: {},
    addEventListener: function (t, fn) { el.listeners[t] = fn; },
    querySelector: function () { return null; },
    querySelectorAll: function () { return []; },
    getAttribute: function () { return null; },
    scrollIntoView: function () {},
    contains: function () { return false; },
  };
  el.classList = {
    add: function (c) { el._cls[c] = 1; },
    remove: function (c) { delete el._cls[c]; },
    contains: function (c) { return !!el._cls[c]; },
    toggle: function (c) { var v = !el._cls[c];
      if (v) el._cls[c] = 1; else delete el._cls[c]; return !v; },
  };
  return el;
}
var __els = {};
var document = {
  getElementById: function (id) {
    if (!__els[id]) __els[id] = __makeEl();
    return __els[id];
  },
  activeElement: null,
};
var sessionStorage = {
  getItem: function () { return null; },
  setItem: function () {}, removeItem: function () {},
};
var location = {
  search: "", origin: "https://plane.test", pathname: "/",
  assign: function (u) { location.assigned = u; },
};
var history = { replaceState: function () {} };
"""


def _node_app_eval(fragment):
    """Evaluate the FULL dashboard script (helpers + app state) with a
    stubbed DOM, then run `fragment` (which may rebind `api` /
    `setTimeout` after script load). Prints one JSON object."""
    harness = _APP_PREAMBLE + "\n" + _script() + "\n" + fragment
    with tempfile.NamedTemporaryFile("w", suffix=".js",
                                     delete=False) as f:
        f.write(harness)
        path = f.name
    try:
        r = subprocess.run(["node", path], capture_output=True, text=True,
                           timeout=30)
    finally:
        os.unlink(path)
    assert r.returncode == 0, "app harness failed:\n%s" % r.stderr
    return json.loads(r.stdout)


def test_showdetail_late_response_does_not_clobber_newer_box():
    """Engineering B1 (#954): opening box B while box A's detail fetch is
    still in flight must not let A's late response overwrite B's card or
    fire loadApprovals(A) into it."""
    o = _node_app_eval("""
var __pendingApi = [];
api = function (path) {
  return new Promise(function (res, rej) {
    __pendingApi.push({ path: path, resolve: res, reject: rej });
  });
};
(async function () {
  showDetail("boxA");   // slow
  showDetail("boxB");   // fast
  __pendingApi[1].resolve({ status: 200, data: { ok: true,
    box: { id: "boxB", name: "Bee", last_status: {} } } });
  await Promise.resolve(); await Promise.resolve();
  var mid = document.getElementById("detail-name").textContent;
  var approvalsCallsMid = __pendingApi.filter(function (p) {
    return p.path.indexOf("/approvals") !== -1;
  }).length;
  __pendingApi[0].resolve({ status: 200, data: { ok: true,
    box: { id: "boxA", name: "Ay", last_status: {} } } });
  await Promise.resolve(); await Promise.resolve();
  var late = document.getElementById("detail-name").textContent;
  var approvalsCallsLate = __pendingApi.filter(function (p) {
    return p.path.indexOf("/approvals") !== -1;
  }).length;
  console.log(JSON.stringify({ mid: mid, late: late,
    approvalsCallsMid: approvalsCallsMid,
    approvalsCallsLate: approvalsCallsLate }));
})();
""")
    assert o["mid"] == "Bee"      # B rendered
    assert o["late"] == "Bee"    # A's late response stayed out
    assert o["approvalsCallsMid"] == 1   # loadApprovals(B) fired
    assert o["approvalsCallsLate"] == 1  # no loadApprovals(A) after it


def test_decide_watchdog_releases_wedged_buttons():
    """Engineering B2 (#954): a decide POST that never settles must not
    wedge the card forever — the 30s watchdog re-enables the buttons,
    surfaces the timeout, and ignores the late response."""
    o = _node_app_eval("""
var __pendingApi = [];
api = function (path, opts) {
  return new Promise(function (res, rej) {
    __pendingApi.push({ resolve: res, reject: rej });
  });
};
var __realSetTimeout = setTimeout;
var __timers = [];
setTimeout = function (fn, ms) { __timers.push(fn); return __timers.length; };
var errEl = __makeEl(), okEl = __makeEl(), b1 = __makeEl(), b2 = __makeEl();
var card = __makeEl();
card.querySelector = function (s) { return s === ".err" ? errEl : okEl; };
card.querySelectorAll = function () { return [b1, b2]; };
card.getAttribute = function () { return "a_1"; };
(async function () {
  decideApproval(card, "box1", "a_1", "approve");
  var disabledAtTap = b1.disabled && b2.disabled;
  var watchdogArmed = __timers.length === 1;
  __timers[0]();  // fire the watchdog: the plane never answered
  var out = {
    disabledAtTap: disabledAtTap,
    watchdogArmed: watchdogArmed,
    reenabled: !b1.disabled && !b2.disabled,
    errShown: errEl.textContent.indexOf("timed out") !== -1 &&
              !errEl.classList.contains("hidden"),
  };
  // A late plane response after the watchdog must be ignored, not crash.
  __pendingApi[0].resolve({ status: 200, data: { ok: true, approval: {} } });
  await new Promise(function (r) { __realSetTimeout(r, 10); });
  out.lateIgnored = !b1.disabled && errEl.textContent.indexOf("timed out") !== -1;
  console.log(JSON.stringify(out));
})();
""")
    assert o["disabledAtTap"] is True
    assert o["watchdogArmed"] is True
    assert o["reenabled"] is True
    assert o["errShown"] is True
    assert o["lateIgnored"] is True


def test_agentid_callback_exchange_lands_agent_view():
    """AgentID callback (?code=&state=): state is validated, the code is
    exchanged with the PKCE verifier (public client — no secret), the
    id_token claims are validated, and the agent view renders the
    owner identity. A state mismatch must fail closed without calling
    the token endpoint."""
    frag = """
var store = {};
sessionStorage.getItem = function (k) { return store[k] || null; };
sessionStorage.setItem = function (k, v) { store[k] = v; };
sessionStorage.removeItem = function (k) { delete store[k]; };
AGENTID.client_id = "cid-123";
function b64url(o) {
  return Buffer.from(JSON.stringify(o)).toString("base64")
    .replace(/\\+/g, "-").replace(/\\//g, "_").replace(/=+$/, "");
}
var payload = { iss: "https://auth.agentid.com", aud: "cid-123",
  actor_type: "agent", nonce: "n-1", iat: 1700, exp: 9999999999,
  owner_sub: "owner-1", owner_email: "owner@example.com" };
var tok = b64url({ alg: "ES256", typ: "JWT" }) + "." +
          b64url(payload) + ".sig";
var fetched = [];
fetch = function (url, opts) {
  fetched.push({ url: url, body: opts.body });
  return Promise.resolve({ ok: true, status: 200, json: function () {
    return Promise.resolve({ id_token: tok });
  } });
};
store["svm_agentid_flow"] = JSON.stringify(
  { state: "st-1", nonce: "n-1", verifier: "verifier-9",
    redirect_uri: "https://plane.test/" });
location.search = "?code=authcode&state=st-1";
(async function () {
  var handled = await finishAgentLogin();
  var dl = document.getElementById("agent-dl").innerHTML;
  var out = {
    handled: handled,
    agentShown: !document.getElementById("agent-view").classList
      .contains("hidden"),
    hasEmail: dl.indexOf("owner@example.com") !== -1,
    hasActor: dl.indexOf(">agent<") !== -1,
    tokenPosts: fetched.length === 1 &&
      fetched[0].url === "https://auth.agentid.com/v0/token",
    sendsCode: fetched[0].body.indexOf("code=authcode") !== -1,
    sendsVerifier: fetched[0].body.indexOf("code_verifier=verifier-9") !== -1,
    sendsClientId: fetched[0].body.indexOf("client_id=cid-123") !== -1,
    noSecret: fetched[0].body.toLowerCase().indexOf("secret") === -1,
    flowCleared: !("svm_agentid_flow" in store),
    sessionSaved: (function () {
      try { return JSON.parse(store["svm_agent_session"]).actor_type === "agent"; }
      catch (e) { return false; }
    })(),
  };
  // Now the hostile case: same code, wrong state — must fail closed.
  fetched = [];
  store["svm_agentid_flow"] = JSON.stringify(
    { state: "st-1", nonce: "n-1", verifier: "verifier-9",
      redirect_uri: "https://plane.test/" });
  location.search = "?code=authcode&state=WRONG";
  await finishAgentLogin();
  out.csrfBlocked = fetched.length === 0 &&
    !document.getElementById("agent-login-err").classList.contains("hidden");
  console.log(JSON.stringify(out));
})();
"""
    o = _node_app_eval(frag)
    assert o["handled"] is True
    assert o["agentShown"] is True
    assert o["hasEmail"] is True
    assert o["hasActor"] is True
    assert o["tokenPosts"] is True
    assert o["sendsCode"] is True
    assert o["sendsVerifier"] is True
    assert o["sendsClientId"] is True
    assert o["noSecret"] is True
    assert o["flowCleared"] is True
    assert o["sessionSaved"] is True
    assert o["csrfBlocked"] is True


def test_view_modes_are_mutually_exclusive():
    """The owner session (app-view) and the agent session (agent-view)
    are mutually exclusive: entering one hides the other and clears its
    credentials/timers, and sign-out restores both sign-in cards."""
    o = _node_app_eval("""
var __pendingApi = [];
api = function (path) {
  return new Promise(function (res) { __pendingApi.push(res); });
};
(async function () {
  var lp = login("svm_x");
  __pendingApi[0]({ status: 200, data: { ok: true, boxes: [] } });
  await lp;
  var out = {
    ownerApp: !document.getElementById("app-view").classList.contains("hidden"),
    ownerAgentCardHidden:
      document.getElementById("agent-login-view").classList.contains("hidden"),
  };
  AGENT = { actor_type: "agent", owner_sub: "o", owner_email: "o@e.com",
            exp: 9999999999, id_token: "t" };
  showAgentView();
  out.agentShown = !document.getElementById("agent-view").classList.contains("hidden");
  out.appHiddenAfterAgent =
    document.getElementById("app-view").classList.contains("hidden");
  out.refreshHiddenAfterAgent =
    document.getElementById("refresh-btn").classList.contains("hidden");
  agentLogout();
  out.backToLogin = !document.getElementById("login-view").classList.contains("hidden");
  out.agentViewHiddenAfterLogout =
    document.getElementById("agent-view").classList.contains("hidden");
  out.agentCardBack =
    !document.getElementById("agent-login-view").classList.contains("hidden");
  console.log(JSON.stringify(out));
})();
""")
    assert o["ownerApp"] is True
    assert o["ownerAgentCardHidden"] is True
    assert o["agentShown"] is True
    assert o["appHiddenAfterAgent"] is True
    assert o["refreshHiddenAfterAgent"] is True
    assert o["backToLogin"] is True
    assert o["agentViewHiddenAfterLogout"] is True
    assert o["agentCardBack"] is True
