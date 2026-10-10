"""Pin hardening response headers across every localhost HTTP surface (#1237).

Manual re-sweeps of the header sets don't converge: every surface hand-rolls
its own headers and they drift (confirmd gained X-Frame-Options in #1227
while its own _send_json still lacked nosniff; tenant_status.py shipped with
zero hardening headers). This test is the machine check.

Policy (issue #1237):
- Every body-sending response on every enumerated surface MUST send:
      X-Content-Type-Options: nosniff
      Referrer-Policy: no-referrer
- Every text/html response MUST additionally send:
      X-Frame-Options: DENY

Deliberate deltas (asserted here, not drift):
- JSON/PNG-only API surfaces (cua-bridge _json/_send_png, fleet/api _send,
  tenant_status _send_json, confirmd _send_json/_deny/_send_sw_js) carry no
  X-Frame-Options: nothing there is framed.
- waitlistd (public landing page + invite-claim) carries no X-Frame-Options:
  the claim flow is token-Bearer <redacted> with no ambient session — framing the page
  grants an attacker no capability beyond what the single-use invite token
  already confers, and a claim only affects the token holder's own row.
  nosniff + no-referrer still apply (asserted; XFO absence pinned too).

Documented exclusions (not required, not asserted):
- stdlib send_error HTML pages: reachable only via malformed requests, no
  interactive content.
- No-body 404s (confirmd do_GET/do_POST) and no-body 303/302 redirects
  (confirmd _answer_locked/_reopen_locked, waitlistd _redirect): Location
  only, no interactive content.
- harness/echo-fixture.py and scripts/generate_demo_assets.py's
  _PushqMockHandler: ephemeral test/demo-only servers, never a product
  surface.

The test works three ways so new paths can't slip in silently:
1. Live: each pinned choke point is invoked on a real handler instance and
   its emitted headers are asserted exactly.
2. Completeness: each in-scope file is AST-scanned for send_response owners;
   the owner set must equal pinned + excluded exactly — a new response path
   fails this test until it is registered (and pinned) here.
3. Surface inventory: a repo-wide scan asserts no new BaseHTTPRequestHandler
   surface exists outside the in-scope + documented-exclusion lists.
"""
import ast
import importlib.util
import io
import sys
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

BASE_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}
HTML_HEADERS = dict(BASE_HEADERS, **{"X-Frame-Options": "DENY"})

_MODULE_FILE = {
    "pin_confirmd": "confirm/confirmd.py",
    "pin_cred_ui": "cred-ui/cred-ui.py",
    "pin_cua_bridge": "cua/bin/cua-bridge.py",
    "pin_tenant_status": "hosted/tenant_status.py",
    "pin_fleet_api": "fleet/api.py",
    "pin_waitlistd": "site/waitlistd.py",
}


def _load(name, relpath):
    spec = importlib.util.spec_from_file_location(
        name, str(REPO / relpath))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# Extra sys.path entries the surface modules need for their own imports.
# Saved/restored so this cross-component test never leaks path state.
@contextmanager
def _surface_path():
    saved = list(sys.path)
    for entry in ("scripts", "credlib", "fleet"):
        path = str(REPO / entry)
        if path not in sys.path:
            sys.path.insert(0, path)
    try:
        yield
    finally:
        sys.path[:] = saved


with _surface_path():
    _MODS = {name: _load(name, rel)
             for name, rel in _MODULE_FILE.items()}


class _Capture:
    """Minimal handler stand-in: records send_response/send_header."""

    def __init__(self, handler_cls):
        self.h = handler_cls.__new__(handler_cls)
        self.h.wfile = io.BytesIO()
        self.codes = []
        self.headers = {}
        self.h.send_response = lambda code: self.codes.append(code)
        self.h.send_header = lambda k, v: self.headers.__setitem__(k, v)
        self.h.end_headers = lambda: None


def _deny_call(cap):
    # _deny writes the audit trail first; the audit sink is irrelevant to
    # the header contract, so stub it for the duration of the call.
    mod = _MODS["pin_confirmd"]
    real = mod.audit_log
    mod.audit_log = lambda *a, **k: None
    try:
        cap.h._deny("100.99.0.1", None, "self-peer")
    finally:
        mod.audit_log = real


# (module name, handler class, pinned method, invocation, required headers,
#  no-XFO reason)
_PINNED = [
    ("pin_confirmd", "Handler", "_send_html",
     lambda c: c.h._send_html("<p>x</p>"),
     HTML_HEADERS, None),
    ("pin_confirmd", "Handler", "_send_sw_js",
     lambda c: c.h._send_sw_js(),
     BASE_HEADERS, "application/javascript is never framed"),
    ("pin_confirmd", "Handler", "_send_json",
     lambda c: c.h._send_json({"ok": True}),
     BASE_HEADERS, "JSON API; never framed"),
    ("pin_confirmd", "Handler", "_deny", _deny_call,
     BASE_HEADERS, "text/plain 403; never framed"),
    ("pin_cred_ui", "Handler", "_send",
     lambda c: c.h._send(200, {"ok": True}),
     HTML_HEADERS, None),
    ("pin_cua_bridge", "Handler", "_json",
     lambda c: c.h._json({"ok": True}),
     BASE_HEADERS, "API-only bridge; never framed (#1228)"),
    ("pin_cua_bridge", "Handler", "_send_png",
     lambda c: c.h._send_png(b"\x89PNG\r\n\x1a\n"),
     BASE_HEADERS, "screenshot PNG; never framed"),
    ("pin_tenant_status", "TenantStatusHandler", "_send_json",
     lambda c: c.h._send_json(200, {"ok": True}),
     BASE_HEADERS, "JSON status API; never framed"),
    ("pin_fleet_api", "FleetAPIHandler", "_send",
     lambda c: c.h._send(200, {"ok": True}),
     BASE_HEADERS, "JSON API; never framed"),
    ("pin_waitlistd", "_Handler", "_send",
     lambda c: c.h._send(200, "<html></html>"),
     BASE_HEADERS,
     "invite-claim is token-Bearer <redacted>, no ambient session — framing grants no new capability"),
]


def test_pinned_paths_send_required_headers():
    failures = []
    for mod_name, cls_name, _method, invoke, required, _note in _PINNED:
        cap = _Capture(getattr(_MODS[mod_name], cls_name))
        invoke(cap)
        for header, value in required.items():
            got = cap.headers.get(header)
            if got != value:
                failures.append(
                    "%s.%s: %s = %r, want %r"
                    % (mod_name, cls_name, header, got, value))
    assert not failures, "hardening header gaps:\n" + "\n".join(failures)


def test_html_emitters_send_x_frame_options_deny():
    """HTML emitters must not be framable — except waitlistd's public page."""
    emitters = [
        ("pin_confirmd", "Handler", lambda c: c.h._send_html("<p>x</p>")),
        ("pin_cred_ui", "Handler", lambda c: c.h._send(200, {"ok": True})),
    ]
    for mod_name, cls_name, invoke in emitters:
        cap = _Capture(getattr(_MODS[mod_name], cls_name))
        invoke(cap)
        assert cap.headers.get("X-Frame-Options") == "DENY", \
            "%s.%s must send X-Frame-Options: DENY" % (mod_name, cls_name)


def test_waitlistd_deliberately_sends_no_x_frame_options():
    """The waitlistd 'no X-Frame-Options' delta is machine-checked in both
    directions: the invite-claim flow is token-Bearer <redacted> with no ambient
    session, so framing grants no new capability — but if XFO ever appears
    here the suite must say so loudly rather than silently changing the
    page's framing posture."""
    cap = _Capture(_MODS["pin_waitlistd"]._Handler)
    cap.h._send(200, "<html></html>")
    assert "X-Frame-Options" not in cap.headers, \
        "waitlistd framing posture changed — deliberate, re-justify or revert"


# ---------------------------------------------------------------------------
# Completeness: every send_response owner is pinned or excluded, exactly.


_EXCLUDED_OWNERS = {
    "confirm/confirmd.py": {
        "do_GET": "no-body 404s only",
        "do_POST": "no-body 404 only",
        "_answer_locked": "no-body 303 redirect (Location only)",
        "_reopen_locked": "no-body 303 redirects (Location only)",
    },
    "site/waitlistd.py": {
        "_redirect": "no-body 302 redirect (Location only; already sends "
                     "Referrer-Policy: no-referrer)",
    },
}

_IN_SCOPE = list(_MODULE_FILE.values())

_EXCLUDED_FILES = {
    # Ephemeral test/demo-only servers, never product surfaces.
    "harness/echo-fixture.py": "test fixture",
    "scripts/generate_demo_assets.py": "demo-asset generator mock",
}


def _send_response_owners(path):
    tree = ast.parse((REPO / path).read_text())
    owners = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for sub in ast.walk(node):
                if (isinstance(sub, ast.Call)
                        and isinstance(sub.func, ast.Attribute)
                        and sub.func.attr == "send_response"
                        and isinstance(sub.func.value, ast.Name)
                        and sub.func.value.id == "self"):
                    owners.add(node.name)
    return owners


def _pinned_owner_names():
    """Pinned method names per source file, straight from the pin table."""
    names = {}
    for mod_name, _cls, method, _invoke, _req, _note in _PINNED:
        names.setdefault(_MODULE_FILE[mod_name], set()).add(method)
    return names


def test_no_unpinned_send_response_owner():
    """A new response path must be registered (pinned or excluded) here."""
    pinned_by_file = _pinned_owner_names()
    for path in _IN_SCOPE:
        owners = _send_response_owners(path)
        pinned = pinned_by_file.get(path, set())
        excluded = set(_EXCLUDED_OWNERS.get(path, {}))
        unregistered = owners - pinned - excluded
        stale = (pinned | excluded) - owners
        assert not unregistered, \
            "%s: unregistered send_response owner(s) %s — pin or exclude" \
            % (path, sorted(unregistered))
        assert not stale, \
            "%s: stale registration(s) %s — method no longer sends responses" \
            % (path, sorted(stale))


def _handler_base_names(tree):
    """Names that can refer to BaseHTTPRequestHandler in this module:
    the bare name plus any `as`-aliases from from-imports."""
    names = {"BaseHTTPRequestHandler"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "BaseHTTPRequestHandler" and alias.asname:
                    names.add(alias.asname)
    return names


def test_every_handler_surface_is_registered():
    """No new BaseHTTPRequestHandler surface outside the known lists."""
    found = set()
    for path in REPO.rglob("*.py"):
        if ".git" in path.parts or "__pycache__" in path.parts:
            continue
        if path.name.startswith("test_"):
            # Test doubles subclass the handler for fakes — never product
            # surfaces, never shipped; the product inventory is what matters.
            continue
        try:
            tree = ast.parse(path.read_text())
        except (OSError, SyntaxError):
            continue
        names = _handler_base_names(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and any(
                    (isinstance(b, ast.Name) and b.id in names)
                    or (isinstance(b, ast.Attribute)
                        and b.attr == "BaseHTTPRequestHandler")
                    for b in node.bases):
                found.add(str(path.relative_to(REPO)))
                break
    known = set(_IN_SCOPE) | set(_EXCLUDED_FILES)
    assert found == known, \
        "unregistered handler surface(s): %s" % sorted(found - known)
