"""Tests for cua/bin/cua-bridge.py — the localhost CUA driver bridge.

Nothing here touches a real driver, display, or network: the bridge's
`call()` (which shells out to `cua-driver`) is stubbed per test, and
`launch_app()`'s shutil/subprocess probes are patched. What is under
test is the pure decision logic:

- which window a click/type/key lands on (`top_window_at`, `top_window`,
  `focus_window`) — the panel/desktop misrouting this logic prevents is
  a real mis-click class on the XFCE desktop;
- the CSRF/host allowlist (`Handler._csrf_ok`) — the bridge's security
  boundary against malicious web pages reaching it through the
  operator's SSH tunnel;
- the launch allowlist (`launch_app`) — the other security boundary:
  only fixed, allowlisted apps may be spawned on :98.

The module is loaded by path (it is `cua-bridge.py`, not an importable
package) with plain exec_module — no sys.modules registration, per the
repo's test convention.
"""

import importlib.util
import os

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRIDGE_PATH = os.path.join(REPO_ROOT, "cua", "bin", "cua-bridge.py")


def _load_bridge():
    # Load by path (cua-bridge.py is not an importable package). No
    # sys.modules registration: the module has no dataclasses or relative
    # imports, so plain exec_module is sufficient, and the repo's test
    # convention forbids leaving sys.modules mutations behind.
    spec = importlib.util.spec_from_file_location("cua_bridge_under_test", BRIDGE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bridge = _load_bridge()


# ---------------------------------------------------------------------------
# window-picking fixtures
# ---------------------------------------------------------------------------

def _win(title, x, y, w, h, z, app="xterm", pid=1000, on_screen=True):
    return {
        "title": title,
        "app_name": app,
        "pid": pid,
        "window_id": 100 + z,
        "is_on_screen": on_screen,
        "z_index": z,
        "bounds": {"x": x, "y": y, "width": w, "height": h},
    }


def _stub_call(monkeypatch, windows):
    seen = []

    def fake(tool, args):
        seen.append((tool, args))
        assert tool == "list_windows"
        return {"windows": windows}

    monkeypatch.setattr(bridge, "call", fake)
    return seen


# ---------------------------------------------------------------------------
# top_window_at
# ---------------------------------------------------------------------------

def test_top_window_at_picks_highest_z_index_hit(monkeypatch):
    wins = [
        _win("back", 0, 0, 800, 600, z=1, pid=101),
        _win("front", 100, 100, 200, 200, z=5, pid=102),
    ]
    _stub_call(monkeypatch, wins)
    assert bridge.top_window_at(150, 150)["title"] == "front"


def test_top_window_at_ignores_windows_without_pid(monkeypatch):
    wins = [_win("ghost", 0, 0, 800, 600, z=9, pid=None)]
    _stub_call(monkeypatch, wins)
    assert bridge.top_window_at(10, 10) is None


def test_top_window_at_ignores_offscreen_windows(monkeypatch):
    wins = [_win("hidden", 0, 0, 800, 600, z=9, on_screen=False)]
    _stub_call(monkeypatch, wins)
    assert bridge.top_window_at(10, 10) is None


def test_top_window_at_edge_containment(monkeypatch):
    # left/top edges are inclusive, right/bottom edges exclusive —
    # a click at x == bounds.x + width belongs to the neighbor, not this one.
    wins = [_win("box", 100, 100, 200, 200, z=1)]
    _stub_call(monkeypatch, wins)
    assert bridge.top_window_at(100, 100)["title"] == "box"
    assert bridge.top_window_at(299, 299)["title"] == "box"
    assert bridge.top_window_at(300, 150) is None
    assert bridge.top_window_at(150, 300) is None


def test_top_window_at_none_when_no_hit(monkeypatch):
    wins = [_win("elsewhere", 500, 500, 100, 100, z=1)]
    _stub_call(monkeypatch, wins)
    assert bridge.top_window_at(10, 10) is None


# ---------------------------------------------------------------------------
# top_window
# ---------------------------------------------------------------------------

def test_top_window_skips_desktop_and_panel(monkeypatch):
    # With plain max(z_index) the always-on-top panel would swallow
    # type/key input meant for a real window (seen on the XFCE desktop).
    wins = [
        _win("real", 0, 0, 800, 600, z=3, app="xterm", pid=101),
        _win("panel", 0, 0, 1920, 30, z=99, app="Xfce4-panel", pid=50),
        _win("desktop", 0, 0, 1920, 1080, z=98, app="Xfdesktop", pid=51),
    ]
    _stub_call(monkeypatch, wins)
    assert bridge.top_window()["title"] == "real"


def test_top_window_picks_highest_app_window(monkeypatch):
    wins = [
        _win("a", 0, 0, 100, 100, z=2, pid=101),
        _win("b", 0, 0, 100, 100, z=7, pid=102),
    ]
    _stub_call(monkeypatch, wins)
    assert bridge.top_window()["title"] == "b"


def test_top_window_falls_back_to_panel_when_nothing_else(monkeypatch):
    wins = [_win("panel", 0, 0, 1920, 30, z=99, app="Xfce4-panel", pid=50)]
    _stub_call(monkeypatch, wins)
    assert bridge.top_window()["title"] == "panel"


def test_top_window_none_when_no_pid(monkeypatch):
    wins = [_win("ghost", 0, 0, 100, 100, z=1, pid=None)]
    _stub_call(monkeypatch, wins)
    assert bridge.top_window() is None


def test_top_window_pid_none_when_no_window(monkeypatch):
    _stub_call(monkeypatch, [])
    assert bridge.top_window_pid() is None


def test_focus_window_activates_by_pid_and_window_id(monkeypatch):
    w = _win("real", 0, 0, 800, 600, z=3, pid=4242)
    seen = []

    def fake(tool, args):
        seen.append((tool, args))
        return {}

    monkeypatch.setattr(bridge, "call", fake)
    bridge.focus_window(w)
    assert seen == [("bring_to_front", {"pid": 4242, "window_id": w["window_id"]})]


# ---------------------------------------------------------------------------
# CSRF / host allowlist
# ---------------------------------------------------------------------------

def _handler(command="GET", host="127.0.0.1:18731", csrf=None):
    h = bridge.Handler.__new__(bridge.Handler)
    headers = {}
    if host is not None:
        headers["Host"] = host
    if csrf is not None:
        headers["X-CUA"] = csrf
    h.headers = headers
    h.command = command
    return h


@pytest.mark.parametrize("host", [
    "127.0.0.1:18731",
    "localhost:18731",
    "127.0.0.1:18732",   # local end of the operator SSH tunnel
    "localhost:18732",
    "LOCALHOST:18731",   # host match is case-insensitive
])
def test_csrf_ok_accepts_allowlisted_hosts(host):
    assert _handler("GET", host=host)._csrf_ok() is True


@pytest.mark.parametrize("host", [
    "evil.example:18731",
    "127.0.0.1:9999",
    "127.0.0.1:18731.evil.example",
    "evil.example, 127.0.0.1:18731",  # first Host entry wins; evil stays evil
])
def test_csrf_ok_rejects_non_allowlisted_hosts(host):
    assert _handler("GET", host=host)._csrf_ok() is False


def test_csrf_ok_rejects_missing_host_header():
    assert _handler("GET", host=None)._csrf_ok() is False


def test_csrf_ok_get_needs_no_custom_header():
    assert _handler("GET", host="127.0.0.1:18731")._csrf_ok() is True


def test_csrf_ok_post_requires_header():
    assert _handler("POST", host="127.0.0.1:18731")._csrf_ok() is False
    assert _handler("POST", host="127.0.0.1:18731", csrf="0")._csrf_ok() is False
    assert _handler("POST", host="127.0.0.1:18731", csrf="1")._csrf_ok() is True


def test_csrf_ok_post_still_checks_host():
    h = _handler("POST", host="evil.example", csrf="1")
    assert h._csrf_ok() is False


# ---------------------------------------------------------------------------
# launch allowlist
# ---------------------------------------------------------------------------

def test_launch_app_rejects_non_allowlisted_app(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("must not spawn anything for a rejected app")

    monkeypatch.setattr(bridge.subprocess, "Popen", boom)
    with pytest.raises(ValueError, match="not allowlisted"):
        bridge.launch_app("firefox")


def test_launch_app_rejects_allowlisted_app_with_missing_binary(monkeypatch):
    monkeypatch.setattr(bridge.shutil, "which", lambda argv0: None)
    monkeypatch.setattr(bridge.os.path, "isfile", lambda p: False)
    with pytest.raises(RuntimeError, match="not installed"):
        bridge.launch_app("xterm")


def test_launch_app_spawns_allowlisted_app_with_x11_env(monkeypatch):
    captured = {}

    def fake_which(argv0):
        return "/usr/bin/" + argv0

    def fake_popen(argv, **kwargs):
        captured["argv"] = argv
        captured.update(kwargs)

        class P:
            pid = 1234

        return P()

    monkeypatch.setattr(bridge.shutil, "which", fake_which)
    monkeypatch.setattr(bridge.subprocess, "Popen", fake_popen)
    assert bridge.launch_app("xterm") == {"launched": "xterm"}
    assert captured["argv"][0] == "xterm"
    env = captured["env"]
    assert env["GDK_BACKEND"] == "x11"
    assert env["XDG_SESSION_TYPE"] == "x11"
    assert "WAYLAND_DISPLAY" not in env
    assert captured["start_new_session"] is True
    assert captured["stdout"] is bridge.subprocess.DEVNULL
    assert captured["stderr"] is bridge.subprocess.DEVNULL


# ---------------------------------------------------------------------------
# do_POST wiring (these routes previously had zero coverage: a removed CSRF
# gate or a deleted panel special-case escaped every test — QA blocker 1)
# ---------------------------------------------------------------------------

def _post_handler(monkeypatch, path, body, windows, host="127.0.0.1:18731",
                  csrf="1"):
    """A Handler ready for do_POST with canned list_windows/click drivers."""
    seen = []

    def fake(tool, args):
        seen.append((tool, args))
        if tool == "list_windows":
            return {"windows": windows}
        return {"ok": True}

    monkeypatch.setattr(bridge, "call", fake)
    h = _handler(command="POST", host=host, csrf=csrf)
    h.path = path
    h._body = lambda: body
    sent = []
    h._json = lambda obj, code=200: sent.append((code, obj))
    return h, sent, seen


def test_post_click_panel_uses_desktop_scope_absolute_coords(monkeypatch):
    panel = _win("top panel", 0, 0, 1920, 30, z=999, app="Xfce4-panel", pid=9)
    h, sent, seen = _post_handler(monkeypatch, "/api/click",
                                  {"x": 50, "y": 10}, [panel])
    h.do_POST()
    clicks = [args for tool, args in seen if tool == "click"]
    # XSendEvent clicks die on the panel: absolute XTEST click, no pid.
    assert clicks == [{"x": 50, "y": 10, "button": "left",
                       "scope": "desktop"}]
    assert sent[0][0] == 200 and sent[0][1]["ok"] is True


def test_post_click_window_uses_window_relative_coords(monkeypatch):
    w = _win("editor", 100, 200, 800, 600, z=3, pid=7)
    h, sent, seen = _post_handler(monkeypatch, "/api/click",
                                  {"x": 150, "y": 230}, [w])
    h.do_POST()
    clicks = [args for tool, args in seen if tool == "click"]
    assert clicks == [{"pid": 7, "window_id": w["window_id"],
                       "x": 50, "y": 30, "button": "left"}]
    assert "scope" not in clicks[0]
    assert sent[0][0] == 200


def test_post_click_evil_host_blocked_before_driver(monkeypatch):
    w = _win("editor", 0, 0, 800, 600, z=1, pid=7)
    h, sent, seen = _post_handler(monkeypatch, "/api/click", {"x": 1, "y": 1},
                                  [w], host="evil.example:18731")
    h.do_POST()
    assert sent == [(403, {"error": "forbidden"})]
    assert seen == []  # the driver was never touched


def test_post_launch_empty_app_rejected(monkeypatch):
    h, sent, seen = _post_handler(monkeypatch, "/api/launch", {"app": ""}, [])
    h.do_POST()
    assert sent == [(400, {"error": "empty app"})]
    assert seen == []


def test_post_type_routes_through_focus_and_foreground(monkeypatch):
    w = _win("editor", 0, 0, 800, 600, z=5, pid=11)
    h, sent, seen = _post_handler(monkeypatch, "/api/type",
                                  {"text": "hello"}, [w])
    h.do_POST()
    assert [tool for tool, _ in seen] == ["list_windows", "bring_to_front",
                                          "type_text"]
    _, type_args = seen[2]
    assert type_args["delivery_mode"] == "foreground"
    assert type_args["text"] == "hello"
    assert sent[0][0] == 200


@pytest.mark.parametrize("command", ["PUT", "DELETE"])
def test_csrf_ok_write_methods_require_header(command):
    assert _handler(command, csrf="1")._csrf_ok() is True
    assert _handler(command, csrf="0")._csrf_ok() is False
    assert _handler(command, csrf=None)._csrf_ok() is False


def test_body_too_large_returns_none():
    h = _handler("POST")
    h.headers = {"Content-Length": "1000001"}
    assert h._body() is None
