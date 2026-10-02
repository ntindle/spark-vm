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
  (esc/relTime/until/isStale/fmtUptime/statusChip/shortId) are
  unit-tested in node by extracting the helper block and stubbing the
  browser globals they touch.
"""
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


def test_byte_identity_fails_when_html_drifts(tmp_path, monkeypatch):
    # Acceptance pin for #858: with a worker reachable, an edit to
    # dashboard.html that skips the re-inline must fail the assertion.
    w = _scratch_worker(str(tmp_path / "worker.py"))
    mutated = str(tmp_path / "mutated.html")
    with open(mutated, "w", encoding="utf-8") as f:
        f.write(_html() + "\n<!-- un-synced edit -->\n")
    monkeypatch.setattr(_THIS, "HTML_PATH", mutated)
    with pytest.raises(AssertionError):
        assert _inline_html(w) == _html()
    # And the sync path restores it.
    real = _scratch_worker(str(tmp_path / "worker2.py"))
    assert _inline_html(real) == _html()


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
                  "pairing-list", "key-input", "login-form", "logout-btn",
                  "refresh-btn"):
        assert 'id="%s"' % token in html, "missing #%s" % token


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

    Renders the fleet-row template with a hostile name through node by
    reusing esc() + shortId() + statusChip() — the same functions the
    page uses — and asserts no raw markup survives."""
    script = _script()
    helpers = script.split("/* ---- app state ---- */")[0]
    harness = helpers + """
const b = {id: 'box_1"><img src=x onerror=alert(1)>', name: '<script>alert(2)</script>', last_heartbeat_at: 1290};
const now = 1300;
const row = '<div class="boxrow" data-id="' + esc(b.id) + '">' +
  '<span class="grow"><span class="name">' + esc(b.name) + '</span> ' +
  '<span class="id">' + esc(shortId(b.id)) + '</span></span>' +
  statusChip(b, now) + '</div>';
console.log(JSON.stringify({row}));
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
    assert r.returncode == 0, r.stderr
    import json
    row = json.loads(r.stdout)["row"]
    assert "<script>" not in row and "<img" not in row
    assert "&lt;script&gt;" in row
