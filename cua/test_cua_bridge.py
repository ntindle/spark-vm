"""Tests for cua/bin/cua-bridge.py — the localhost HTTP bridge to the CUA driver.

Hermetic: no driver binary, no display, no real network beyond a loopback
test server. The bridge module is loaded by path (hyphenated filename) and
its subprocess entry points are monkeypatched away.

Covers:
  - launch allowlist (reject unknown, reject missing binary, spawn contract)
  - top_window_at / top_window window-picking rules
  - CSRF/host gate matrix
  - request-body limits and parsing
  - end-to-end HTTP: click/type/key/launch endpoints incl. the
    desktop-coordinate -> window-relative mapping and the Xfce4-panel
    global-click branch
  - shell-script syntax/shebang/executable-bit for cua/bin/*.sh
  - #493: desktop env file trust (owner/mode/symlink gate; fail-safe skip
    with a loud warning; sane defaults when untrusted/missing)
  - #495: bridge singleton flock (same-process + cross-process exclusion,
    release-on-close, lock file creation)
- #492: XTEST keyboard-path liveness probe (xev KeyPress echo on :98);
  GET /api/status reports "input": {"state": "ok"|"wedged"|"unknown",
  "checked_at", "driver"} — plain status is a pure read serving the cached
  outcome, GET /api/status?probe=1 runs a fresh probe single-flight;
  windows matched by child PID (never title), probe failures / budget
  overruns / late windows are "unknown", never "wedged"
- #494: focus assertion before keystroke delivery — /api/type and /api/key
  re-verify the target window still holds _NET_ACTIVE_WINDOW after
  bring_to_front (one re-focus retry); a persistent mismatch fails closed
  (409, no keystrokes sent) while an unreadable focus property fails open
  loudly; the #492 probe reports stolen focus as "unknown", never a wedge
- #1574: GET /api/status?probe=1 is a state-changing GET — it requires the
  X-CUA CSRF header like the POSTs (GET is a simple request browsers never
  preflight); plain /api/status stays a headerless read-only GET
- #1575: malformed driver window dicts (missing pid/window_id/title, or a
  bounds dict with non-numeric x/y/width/height) are skipped at the filter
  stage with a stderr line instead of KeyError/TypeError-ing into a 500
- #1579: int(float("inf")) overflows instead of ValueError-ing — an
  infinite driver window_id is filtered as malformed (and non-finite
  /api/click coordinates answer 400 "bad coordinates", not 500)
- #1580: the #492 probe's window pick runs through the same #1575 shape
- #1583: non-numeric/negative Content-Length answers 400 "bad content-length"
  (bad-coordinates contract), never 500 with the int() exception text echoed
  filter — a malformed xev candidate is dropped before the PID match and
  the z-order max, so it can never be focused or crash the probe
"""
import importlib.util
import io
import json
import os
import stat
import subprocess
import sys
import threading
import time
from email.message import Message
from http.client import HTTPConnection
from types import SimpleNamespace

import pytest

CUA_DIR = os.path.dirname(os.path.abspath(__file__))
BRIDGE = os.path.join(CUA_DIR, "bin", "cua-bridge.py")


def load_bridge():
    spec = importlib.util.spec_from_file_location("cua_bridge", BRIDGE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def bridge(tmp_path, monkeypatch):
    mod = load_bridge()
    # hermetic registry: the bridge module persists its launch registry to
    # ~/.cache on every spawn (#491) — redirect it to a per-test tmp file
    # and start from an empty registry, so tests never touch (or inherit)
    # real bridge state on machines where the bridge has run.
    mod._LAUNCHED.clear()
    mod._LAUNCH_REGISTRY_FILE = str(tmp_path / "cua-launched.json")
    # hermetic focus assertion (#494): _active_window_id reads the real X
    # server through libX11 — stub it to "unverifiable" (the fail-open
    # path) so no test ever touches a display; individual tests override.
    monkeypatch.setattr(mod, "_active_window_id", lambda: None)
    return mod


WINDOWS = [
    {"pid": 11, "window_id": 101, "app_name": "Xfdesktop", "title": "Desktop",
     "is_on_screen": True, "z_index": 0,
     "bounds": {"x": 0, "y": 0, "width": 1920, "height": 1080}},
    {"pid": 22, "window_id": 202, "app_name": "xterm", "title": "term",
     "is_on_screen": True, "z_index": 1,
     "bounds": {"x": 40, "y": 40, "width": 800, "height": 600}},
    {"pid": 33, "window_id": 303, "app_name": "chromium", "title": "web",
     "is_on_screen": True, "z_index": 2,
     "bounds": {"x": 10, "y": 30, "width": 1260, "height": 740}},
    {"pid": 44, "window_id": 404, "app_name": "Xfce4-panel", "title": "panel",
     "is_on_screen": True, "z_index": 5,
     "bounds": {"x": 0, "y": 1050, "width": 1920, "height": 30}},
]


class FakeDriver:
    """Stands in for bridge.call: records (tool, args), serves windows."""

    def __init__(self, windows):
        self.windows = windows
        self.calls = []

    def __call__(self, tool, args):
        self.calls.append((tool, args))
        if tool == "list_windows":
            return {"windows": self.windows}
        return {"ok": True}


def fake_handler(bridge, command="GET", headers=None, path="/"):
    h = bridge.Handler.__new__(bridge.Handler)
    h.command = command
    h.path = path
    m = Message()
    for k, v in (headers or {}).items():
        m[k] = v
    h.headers = m
    return h


# ---------------------------------------------------------------- launch_app


class TestLaunchApp:
    def test_rejects_unknown_app(self, bridge):
        with pytest.raises(ValueError, match="not allowlisted"):
            bridge.launch_app("evil-app")

    def test_allowlist_contains_exactly_expected_apps(self, bridge):
        # The allowlist is the security boundary for GUI spawning: pin its
        # exact contents so a new entry (e.g. a shell) can't slip in silently.
        assert set(bridge.LAUNCH_ALLOWLIST) == {
            "xterm", "terminal", "chromium", "blender"}
        assert bridge.LAUNCH_ALLOWLIST["xterm"] == [
            "xterm", "-geometry", "100x30+40+40"]
        assert bridge.LAUNCH_ALLOWLIST["terminal"] == [
            "xfce4-terminal", "--geometry=100x30+40+40"]
        chrome = bridge.LAUNCH_ALLOWLIST["chromium"]
        assert chrome[0].endswith("chrome-linux64/chrome")
        # --no-sandbox is a deliberate sandbox-weakening flag (root-owned
        # Chromium under Xvfb); pin it so it can't be added OR removed
        # without a loud test failure.
        assert "--no-sandbox" in chrome
        assert "--window-size=1260,740" in chrome
        assert "--window-position=10,30" in chrome
        assert bridge.LAUNCH_ALLOWLIST["blender"] == [
            os.path.join(os.path.expanduser("~"),
                         "cua/bin/launch-blender-gui.sh")]

    def test_rejects_app_whose_binary_is_missing(self, bridge, monkeypatch):
        monkeypatch.setattr(bridge, "LAUNCH_ALLOWLIST",
                            {"ghost": ["/nonexistent/ghost-bin-xyz"]})
        with pytest.raises(RuntimeError, match="not installed"):
            bridge.launch_app("ghost")

    def test_spawns_allowlisted_app_with_sandbox_env(self, bridge, monkeypatch):
        spawned = {}

        def fake_popen(argv, **kw):
            spawned["argv"] = argv
            spawned.update(kw)
            return SimpleNamespace(pid=1234)

        monkeypatch.setattr(bridge, "LAUNCH_ALLOWLIST",
                            {"demo": [sys.executable, "-c", "pass"]})
        monkeypatch.setattr(bridge.shutil, "which", lambda p: p)
        monkeypatch.setattr(subprocess, "Popen", fake_popen)
        assert bridge.launch_app("demo") == {"launched": "demo"}
        assert spawned["argv"] == [sys.executable, "-c", "pass"]
        assert spawned["env"]["GDK_BACKEND"] == "x11"
        assert spawned["env"]["XDG_SESSION_TYPE"] == "x11"
        assert "WAYLAND_DISPLAY" not in spawned["env"]
        assert spawned["start_new_session"] is True
        assert spawned["stdout"] is subprocess.DEVNULL


# ---------------------------------------------------------------- window picking


class TestTopWindowAt:
    def _call(self, bridge, monkeypatch, windows):
        monkeypatch.setattr(bridge, "call", FakeDriver(windows))

    def test_picks_highest_z_index_among_hits(self, bridge, monkeypatch):
        self._call(bridge, monkeypatch, WINDOWS)
        w = bridge.top_window_at(50, 50)  # inside xterm, chromium, desktop
        assert w["app_name"] == "chromium"

    def test_point_outside_app_window_hits_desktop(self, bridge, monkeypatch):
        self._call(bridge, monkeypatch, WINDOWS)
        w = bridge.top_window_at(1900, 1000)  # desktop only
        assert w["app_name"] == "Xfdesktop"

    def test_point_off_desktop_returns_none(self, bridge, monkeypatch):
        self._call(bridge, monkeypatch, WINDOWS)
        assert bridge.top_window_at(2000, 1100) is None

    def test_right_bottom_edge_is_exclusive(self, bridge, monkeypatch):
        # bounds are [x, x+width): the pixel AT x+width is outside.
        wins = [dict(WINDOWS[1])]  # xterm only, no desktop under it
        self._call(bridge, monkeypatch, wins)
        assert bridge.top_window_at(839, 100)["app_name"] == "xterm"
        assert bridge.top_window_at(840, 100) is None

    def test_windows_without_pid_are_skipped(self, bridge, monkeypatch):
        orphan = dict(WINDOWS[2])
        del orphan["pid"]
        self._call(bridge, monkeypatch, [orphan])
        assert bridge.top_window_at(50, 50) is None

    def test_off_screen_windows_are_skipped(self, bridge, monkeypatch):
        hidden = dict(WINDOWS[2])
        hidden["is_on_screen"] = False
        self._call(bridge, monkeypatch, [hidden, WINDOWS[1]])
        w = bridge.top_window_at(50, 50)
        assert w["app_name"] == "xterm"

    # #1575: malformed driver window dicts must not KeyError/TypeError into
    # a 500 — they are skipped at the filter stage with a stderr line.
    def test_window_missing_bounds_is_skipped(self, bridge, monkeypatch):
        bad = dict(WINDOWS[1])
        del bad["bounds"]
        self._call(bridge, monkeypatch, [bad])
        assert bridge.top_window_at(50, 50) is None

    def test_window_missing_window_id_is_skipped(self, bridge, monkeypatch):
        bad = dict(WINDOWS[1])
        del bad["window_id"]
        self._call(bridge, monkeypatch, [bad])
        assert bridge.top_window_at(50, 50) is None

    def test_window_missing_title_is_skipped(self, bridge, monkeypatch):
        bad = dict(WINDOWS[1])
        del bad["title"]
        self._call(bridge, monkeypatch, [bad])
        assert bridge.top_window_at(50, 50) is None

    def test_window_with_string_bounds_is_skipped(self, bridge, monkeypatch):
        # bounds coordinates are compared with <= — a string would
        # TypeError downstream, so it must be skipped at the filter.
        bad = dict(WINDOWS[1])
        bad["bounds"] = dict(bad["bounds"])
        bad["bounds"]["x"] = "40"
        self._call(bridge, monkeypatch, [bad])
        assert bridge.top_window_at(50, 50) is None

    def test_malformed_does_not_shadow_well_formed(self, bridge, monkeypatch):
        bad = dict(WINDOWS[2])
        del bad["bounds"]
        self._call(bridge, monkeypatch, [bad, WINDOWS[1]])
        w = bridge.top_window_at(50, 50)
        assert w["app_name"] == "xterm"

    def test_non_dict_window_is_skipped(self, bridge, monkeypatch):
        self._call(bridge, monkeypatch, ["not-a-window", WINDOWS[1]])
        w = bridge.top_window_at(50, 50)
        assert w["app_name"] == "xterm"

    def test_malformed_window_logs_stderr(self, bridge, monkeypatch, capsys):
        bad = dict(WINDOWS[1])
        del bad["bounds"]
        self._call(bridge, monkeypatch, [bad])
        bridge.top_window_at(50, 50)
        err = capsys.readouterr().err
        assert "malformed window" in err
        assert "bounds" in err

    def test_window_with_string_z_index_is_skipped(self, bridge, monkeypatch,
                                                   capsys):
        # #1575: z_index is order-compared by the sort — a string would
        # TypeError into a 500, so it must be skipped at the filter.
        bad = dict(WINDOWS[1])
        bad["z_index"] = "high"
        self._call(bridge, monkeypatch, [bad])
        assert bridge.top_window_at(50, 50) is None
        assert "z_index" in capsys.readouterr().err

    def test_mixed_z_index_types_do_not_500(self, bridge, monkeypatch):
        # mixed str/int z_index across windows used to TypeError the
        # sort; now the malformed one is skipped and the well-formed
        # window is still picked.
        bad = dict(WINDOWS[2])
        bad["z_index"] = "high"
        self._call(bridge, monkeypatch, [bad, WINDOWS[1]])
        w = bridge.top_window_at(50, 50)
        assert w["app_name"] == "xterm"


class TestTopWindow:
    def test_skips_desktop_and_panel(self, bridge, monkeypatch):
        monkeypatch.setattr(bridge, "call", FakeDriver(WINDOWS))
        assert bridge.top_window()["app_name"] == "chromium"

    def test_falls_back_to_panel_when_no_app_open(self, bridge, monkeypatch):
        monkeypatch.setattr(
            bridge, "call", FakeDriver([WINDOWS[0], WINDOWS[3]]))
        assert bridge.top_window()["app_name"] == "Xfce4-panel"

    def test_none_when_no_windows(self, bridge, monkeypatch):
        monkeypatch.setattr(bridge, "call", FakeDriver([]))
        assert bridge.top_window() is None

    def test_top_window_pid_none_when_empty(self, bridge, monkeypatch):
        monkeypatch.setattr(bridge, "call", FakeDriver([]))
        assert bridge.top_window_pid() is None

    def test_top_window_skips_malformed(self, bridge, monkeypatch):
        # #1575: /api/type and /api/key index w["pid"] and w["window_id"],
        # and focus asserts int(w["window_id"]) — all must be present.
        no_id = dict(WINDOWS[1])
        del no_id["window_id"]
        no_title = dict(WINDOWS[1])
        del no_title["title"]
        monkeypatch.setattr(bridge, "call", FakeDriver([no_id, no_title]))
        assert bridge.top_window() is None

    def test_top_window_skips_non_numeric_window_id(self, bridge, monkeypatch,
                                                    capsys):
        # #1575: _assert_focused does int(w["window_id"]) — a
        # present-but-non-numeric id would ValueError into a 500.
        bad = dict(WINDOWS[1])
        bad["window_id"] = "0xdeadbeef"
        monkeypatch.setattr(bridge, "call", FakeDriver([bad]))
        assert bridge.top_window() is None
        assert "window_id" in capsys.readouterr().err

    def test_top_window_skips_infinite_window_id(self, bridge, monkeypatch,
                                               capsys):
        # #1579: int(float("inf")) raises OverflowError (not
        # ValueError/TypeError) — an infinite driver window_id must be
        # filtered as malformed, not 500 the bridge.
        bad = dict(WINDOWS[1])
        bad["window_id"] = float("inf")
        monkeypatch.setattr(bridge, "call", FakeDriver([bad]))
        assert bridge.top_window() is None
        assert "window_id" in capsys.readouterr().err

    def test_top_window_skips_negative_inf_window_id(self, bridge,
                                                      monkeypatch, capsys):
        # #1579: -inf overflows the same way as +inf.
        bad = dict(WINDOWS[1])
        bad["window_id"] = float("-inf")
        monkeypatch.setattr(bridge, "call", FakeDriver([bad]))
        assert bridge.top_window() is None
        assert "window_id" in capsys.readouterr().err

    def test_top_window_accepts_numeric_string_window_id(self, bridge,
                                                          monkeypatch):
        # int("123") works fine downstream — coercibility, not type, so
        # this must NOT be flagged (no behavior regression).
        ok = dict(WINDOWS[1])
        ok["window_id"] = "123"
        monkeypatch.setattr(bridge, "call", FakeDriver([ok]))
        assert bridge.top_window()["window_id"] == "123"

    def test_top_window_skips_string_z_index(self, bridge, monkeypatch):
        # max() order-compares z_index — mixed str/int would TypeError.
        bad = dict(WINDOWS[1])
        bad["z_index"] = "high"
        monkeypatch.setattr(bridge, "call", FakeDriver([bad]))
        assert bridge.top_window() is None

    def test_top_window_needs_no_bounds(self, bridge, monkeypatch):
        # focus/type/key never touch bounds — bounds stay optional here.
        no_bounds = dict(WINDOWS[1])
        del no_bounds["bounds"]
        monkeypatch.setattr(bridge, "call", FakeDriver([no_bounds]))
        assert bridge.top_window()["app_name"] == "xterm"


# ---------------------------------------------------------------- CSRF / host gate


class TestCsrfGate:
    HOST = "127.0.0.1:18731"

    def test_get_with_bridge_host_ok(self, bridge):
        assert fake_handler(bridge, "GET", {"Host": self.HOST})._csrf_ok()

    def test_post_without_csrf_header_rejected(self, bridge):
        h = fake_handler(bridge, "POST", {"Host": self.HOST})
        assert not h._csrf_ok()

    def test_post_with_csrf_header_ok(self, bridge):
        h = fake_handler(bridge, "POST",
                         {"Host": self.HOST, "X-CUA": "1"})
        assert h._csrf_ok()

    def test_post_with_wrong_csrf_value_rejected(self, bridge):
        h = fake_handler(bridge, "POST",
                         {"Host": self.HOST, "X-CUA": "0"})
        assert not h._csrf_ok()

    def test_unknown_host_rejected(self, bridge):
        h = fake_handler(bridge, "GET", {"Host": "evil.example"})
        assert not h._csrf_ok()

    def test_missing_host_rejected(self, bridge):
        assert not fake_handler(bridge, "GET", {})._csrf_ok()

    def test_host_match_is_case_insensitive(self, bridge):
        h = fake_handler(bridge, "GET", {"Host": "LOCALHOST:18731"})
        assert h._csrf_ok()

    def test_tunnel_local_end_is_allowed(self, bridge):
        h = fake_handler(bridge, "GET", {"Host": "127.0.0.1:18732"})
        assert h._csrf_ok()

    def test_wrong_port_rejected(self, bridge):
        h = fake_handler(bridge, "GET", {"Host": "127.0.0.1:18733"})
        assert not h._csrf_ok()

    # #1574: /api/status?probe=1 is a state-changing GET behind the CSRF
    # gate's blind spot — it spawns xev, hops focus, and injects an XTEST
    # key, but GET is a *simple request* that browsers never preflight.
    def test_probe_get_without_csrf_header_rejected(self, bridge):
        h = fake_handler(bridge, "GET", {"Host": self.HOST},
                         path="/api/status?probe=1")
        assert not h._csrf_ok()

    def test_probe_get_with_csrf_header_ok(self, bridge):
        h = fake_handler(bridge, "GET",
                         {"Host": self.HOST, "X-CUA": "1"},
                         path="/api/status?probe=1")
        assert h._csrf_ok()

    def test_probe_get_wrong_csrf_value_rejected(self, bridge):
        h = fake_handler(bridge, "GET",
                         {"Host": self.HOST, "X-CUA": "0"},
                         path="/api/status?probe=1")
        assert not h._csrf_ok()

    def test_plain_status_get_needs_no_header(self, bridge):
        # the read-only probe cache read stays headerless.
        h = fake_handler(bridge, "GET", {"Host": self.HOST},
                         path="/api/status")
        assert h._csrf_ok()

    def test_status_probe_wrong_value_needs_no_header(self, bridge):
        # probe=0 is not the mutating query — only the exact "1".
        h = fake_handler(bridge, "GET", {"Host": self.HOST},
                         path="/api/status?probe=0")
        assert h._csrf_ok()


# ---------------------------------------------------------------- request body


class TestBody:
    def _h(self, bridge, payload, content_length=None):
        h = fake_handler(bridge, "POST", {"Host": "127.0.0.1:18731",
                                         "X-CUA": "1"})
        if content_length is None:
            content_length = len(payload)
        h.headers["Content-Length"] = str(content_length)
        h.rfile = io.BytesIO(payload)
        return h

    def test_valid_json_parsed(self, bridge):
        h = self._h(bridge, b'{"x": 1}')
        assert h._body() == {"x": 1}

    def test_empty_body_is_empty_object(self, bridge):
        h = self._h(bridge, b"")
        assert h._body() == {}

    def test_invalid_json_is_empty_object(self, bridge):
        h = self._h(bridge, b"not json{{{")
        assert h._body() == {}

    def test_oversize_body_rejected_before_read(self, bridge):
        h = self._h(bridge, b"x", content_length=2_000_000)
        assert h._body() is None

    def _h_garbage(self, bridge, raw_length):
        h = fake_handler(bridge, "POST", {"Host": "127.0.0.1:18731",
                                          "X-CUA": "1"})
        h.headers["Content-Length"] = raw_length
        h.rfile = io.BytesIO(b'{"x": 1}')
        return h

    def test_garbage_content_length_is_bad_length(self, bridge):
        # Issue #1583: a non-numeric Content-Length used to ValueError out
        # of int() into do_POST's outer 500 (exception text echoed).
        h = self._h_garbage(bridge, "abc")
        assert h._body() is h._BAD_CONTENT_LENGTH

    def test_negative_content_length_is_bad_length(self, bridge):
        # A negative length is the same class of client bug as garbage.
        h = self._h_garbage(bridge, "-5")
        assert h._body() is h._BAD_CONTENT_LENGTH


# ---------------------------------------------------------------- end-to-end HTTP


@pytest.fixture()
def live(bridge, monkeypatch):
    """A real bridge HTTP server on loopback, driver stubbed out."""
    driver = FakeDriver(WINDOWS)
    monkeypatch.setattr(bridge, "call", driver)
    srv = bridge.BridgeServer(("127.0.0.1", 0), bridge.Handler)
    port = srv.server_address[1]
    monkeypatch.setattr(bridge, "ALLOWED_HOSTS",
                        bridge.ALLOWED_HOSTS | {f"127.0.0.1:{port}"})
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield bridge, driver, port
    srv.shutdown()
    srv.server_close()


REMOVE = object()


def req(port, method, path, obj=None, headers=None):
    conn = HTTPConnection("127.0.0.1", port, timeout=10)
    hdrs = {"X-CUA": "1"}
    if headers:
        for k, v in headers.items():
            if v is REMOVE:
                hdrs.pop(k, None)
            else:
                hdrs[k] = v
    body = json.dumps(obj).encode() if obj is not None else None
    if body is not None:
        hdrs.setdefault("Content-Type", "application/json")
    conn.request(method, path, body=body, headers=hdrs)
    resp = conn.getresponse()
    data = resp.read()
    conn.close()
    return resp.status, (json.loads(data) if data else None)


class TestEndpoints:
    def test_get_status(self, live, monkeypatch):
        bridge, driver, port = live
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **k: SimpleNamespace(returncode=0, stdout="ok\n",
                                           stderr=""))
        # hermetic: the real probe spawns xev — stub it, assert it rides along
        monkeypatch.setattr(bridge, "get_input_liveness",
                            lambda run_probe=False: ("unknown", "stubbed",
                                                     None))
        status, body = req(port, "GET", "/api/status")
        assert status == 200
        assert body["ok"] is True
        assert body["detail"] == "ok"
        # #491: the running-launch set rides along (empty here)
        assert body["launched"] == {}
        # #492: the input-path liveness probe rides along too
        assert body["input"]["state"] == "unknown"
        assert body["input"]["detail"] == "stubbed"

    def test_get_status_probe_without_csrf_header_403(self, live, monkeypatch):
        # #1574: the mutating probe query cannot ride a simple request.
        bridge, driver, port = live
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **k: SimpleNamespace(returncode=0, stdout="ok\n",
                                           stderr=""))
        status, body = req(port, "GET", "/api/status?probe=1",
                           headers={"X-CUA": REMOVE})
        assert status == 403

    def test_get_status_probe_with_csrf_header_200(self, live, monkeypatch):
        # the keepalive sends X-CUA: 1 — the probe runs (stubbed here).
        bridge, driver, port = live
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **k: SimpleNamespace(returncode=0, stdout="ok\n",
                                           stderr=""))
        monkeypatch.setattr(bridge, "get_input_liveness",
                            lambda run_probe=False: ("unknown", "stubbed",
                                                     None))
        status, body = req(port, "GET", "/api/status?probe=1")
        assert status == 200
        assert body["input"]["detail"] == "stubbed"

    def test_get_windows(self, live):
        bridge, driver, port = live
        status, body = req(port, "GET", "/api/windows")
        assert status == 200
        assert len(body["windows"]) == 4

    def test_unknown_path_404(self, live):
        _, _, port = live
        status, body = req(port, "GET", "/nope")
        assert status == 404

    def test_unknown_path_with_query_string_404(self, live):
        # the query-string normalization must not rescue unknown routes
        _, _, port = live
        status, body = req(port, "GET", "/nope?x=1")
        assert status == 404

    def test_get_windows_ignores_query_string(self, live):
        # F-cua-1: routing is on the parsed path — a query string on a
        # valid endpoint must not 404 (as /api/windows did before the fix)
        _, _, port = live
        status, body = req(port, "GET", "/api/windows?cache=0")
        assert status == 200
        assert len(body["windows"]) == 4

    def test_screenshot_ignores_query_string(self, live, monkeypatch):
        # same F-cua-1 class, via a raw (non-JSON) request
        bridge, driver, port = live

        def fake_call(tool, args):
            assert tool == "get_desktop_state"
            with open(args["screenshot_out_file"], "wb") as f:
                f.write(b"\x89PNG\r\n\x1a\n")
            return {"ok": True}

        monkeypatch.setattr(bridge, "call", fake_call)
        conn = HTTPConnection("127.0.0.1", port, timeout=10)
        conn.request("GET", "/api/screenshot?x=1", headers={"X-CUA": "1"})
        resp = conn.getresponse()
        data = resp.read()
        conn.close()
        assert resp.status == 200
        assert data[:4] == b"\x89PNG"

    def test_post_with_query_string_routed(self, live):
        # F-cua-1: POST endpoints get the same normalization — before the
        # fix, any query string on a POST path 404'd
        bridge, driver, port = live
        status, body = req(port, "POST", "/api/click?x=1",
                           {"x": 50, "y": 50, "button": "left"})
        assert status == 200
        assert body["window"] == "web"


    def test_post_without_csrf_header_403(self, live):
        _, _, port = live
        status, _ = req(port, "POST", "/api/click", {"x": 1, "y": 1},
                        headers={"X-CUA": REMOVE})
        assert status == 403

    def test_post_with_spoofed_host_403(self, live):
        _, _, port = live
        status, _ = req(port, "POST", "/api/click", {"x": 1, "y": 1},
                        headers={"Host": "evil.example"})
        assert status == 403

    def test_click_maps_to_window_relative_coords(self, live):
        bridge, driver, port = live
        status, body = req(port, "POST", "/api/click",
                           {"x": 50, "y": 50, "button": "left"})
        assert status == 200
        assert body["window"] == "web"
        tool, args = driver.calls[-1]
        assert tool == "click"
        assert args == {"pid": 33, "window_id": 303,
                        "x": 40, "y": 20, "button": "left"}

    def test_click_bad_button_400(self, live):
        _, _, port = live
        status, body = req(port, "POST", "/api/click",
                           {"x": 50, "y": 50, "button": "wheel"})
        assert status == 400

    def test_click_bad_coords_400(self, live):
        # F-cua-5: missing or non-numeric coordinates are a client bug —
        # 400, not a 500 with the exception text echoed. Non-finite
        # coordinates ride the same contract: JSON can carry Infinity
        # (json.loads accepts it) and int(float("inf")) would OverflowError
        # into a 500 without the guard (#1579's sibling case).
        _, _, port = live
        for bad in ({"x": "abc", "y": 1}, {"x": 1}, {"y": 2},
                    {"x": None, "y": 1}, {"x": "3.5", "y": 1},
                    {"x": float("inf"), "y": 1},
                    {"x": 1, "y": float("-inf")}):
            status, body = req(port, "POST", "/api/click", bad)
            assert status == 400, bad
            assert body["error"] == "bad coordinates", bad

    def test_click_no_window_at_point_404(self, live):
        _, _, port = live
        status, body = req(port, "POST", "/api/click",
                           {"x": 2000, "y": 1100})
        assert status == 404

    def test_click_on_panel_uses_desktop_scope(self, live):
        bridge, driver, port = live
        status, body = req(port, "POST", "/api/click",
                           {"x": 100, "y": 1060})
        assert status == 200
        tool, args = driver.calls[-1]
        assert tool == "click"
        assert args == {"x": 100, "y": 1060, "button": "left",
                        "scope": "desktop"}

    def test_type_empty_text_400(self, live):
        _, _, port = live
        status, _ = req(port, "POST", "/api/type", {"text": ""})
        assert status == 400

    def test_type_truncates_at_2000_chars(self, live):
        bridge, driver, port = live
        status, body = req(port, "POST", "/api/type", {"text": "a" * 5000})
        assert status == 200
        tool, args = driver.calls[-1]
        assert tool == "type_text"
        assert len(args["text"]) == 2000

    def test_type_no_window_open_404(self, live, monkeypatch):
        bridge, driver, port = live
        monkeypatch.setattr(bridge, "call", FakeDriver([]))
        status, _ = req(port, "POST", "/api/type", {"text": "hi"})
        assert status == 404

    def test_key_empty_400(self, live):
        _, _, port = live
        status, _ = req(port, "POST", "/api/key", {"key": ""})
        assert status == 400

    def test_key_modifiers_filtered_to_allowlist(self, live):
        bridge, driver, port = live
        status, body = req(port, "POST", "/api/key",
                           {"key": "Enter",
                            "modifiers": ["ctrl", "bogus", "alt"]})
        assert status == 200
        tool, args = driver.calls[-1]
        assert tool == "press_key"
        assert args["modifiers"] == ["ctrl", "alt"]

    def test_launch_unknown_app_400(self, live):
        _, _, port = live
        status, body = req(port, "POST", "/api/launch", {"app": "rm -rf"})
        assert status == 400

    def test_launch_allowlisted_app_200(self, live, monkeypatch):
        bridge, driver, port = live
        monkeypatch.setattr(bridge, "launch_app",
                            lambda name, singleton=False: {"launched": name})
        status, body = req(port, "POST", "/api/launch", {"app": "xterm"})
        assert status == 200
        assert body["result"] == {"launched": "xterm"}

    def test_oversize_body_413(self, live):
        _, _, port = live
        conn = HTTPConnection("127.0.0.1", port, timeout=10)
        conn.request("POST", "/api/click", body=b"x",
                     headers={"X-CUA": "1", "Content-Length": "2000000"})
        resp = conn.getresponse()
        assert resp.status == 413
        conn.close()

    def test_garbage_content_length_400(self, live):
        # Issue #1583: garbage Content-Length is a client bug (400, the
        # bad-coordinates contract), never a 500 with the int() exception
        # text echoed.
        _, _, port = live
        status, body = req(port, "POST", "/api/click", {"x": 1, "y": 2},
                           headers={"Content-Length": "abc"})
        assert status == 400
        assert body["error"] == "bad content-length"


# ---------------------------------------------------------------- #494 focus assertion


class TestFocusAssertion:
    """#494: the focus-then-type/key TOCTOU — bring_to_front is async and
    focus can be stolen before injection, so the bridge re-verifies
    _NET_ACTIVE_WINDOW before delivering keystrokes."""

    def _window(self):
        return {"pid": 33, "window_id": 303, "title": "web"}

    def test_match_on_first_poll_no_retry(self, bridge, monkeypatch):
        monkeypatch.setattr(bridge, "_active_window_id", lambda: 303)
        monkeypatch.setattr(bridge, "_FOCUS_SETTLE_S", 0.05)
        focuses = []
        monkeypatch.setattr(bridge, "focus_window", focuses.append)
        assert bridge._assert_focused(self._window()) is True
        assert focuses == []  # no retry needed when focus already holds

    def test_retry_then_match(self, bridge, monkeypatch):
        # slow WM / transient raise: wrong id until the re-assert lands,
        # then the target — succeeds with exactly one re-focus
        state = {"refocused": False}

        def fake_active():
            return 303 if state["refocused"] else 101

        def fake_focus(w):
            state["refocused"] = True

        monkeypatch.setattr(bridge, "_active_window_id", fake_active)
        monkeypatch.setattr(bridge, "focus_window", fake_focus)
        monkeypatch.setattr(bridge, "_FOCUS_SETTLE_S", 0.05)
        monkeypatch.setattr(bridge, "_FOCUS_POLL_STEP_S", 0.01)
        assert bridge._assert_focused(self._window()) is True

    def test_persistent_mismatch_fails_closed(self, bridge, monkeypatch):
        monkeypatch.setattr(bridge, "_active_window_id", lambda: 999)
        monkeypatch.setattr(bridge, "_FOCUS_SETTLE_S", 0.05)
        monkeypatch.setattr(bridge, "_FOCUS_POLL_STEP_S", 0.01)
        focuses = []
        monkeypatch.setattr(bridge, "focus_window", focuses.append)
        assert bridge._assert_focused(self._window()) is False
        assert len(focuses) == 1  # exactly one re-assert, then give up

    def test_readable_then_unreadable_stays_fail_closed(
            self, bridge, monkeypatch):
        # Architecture-review regression: a readable wrong id (the
        # stolen-focus signal) followed by transient unreadable reads
        # must NOT downgrade to fail-open — the signal survives the X
        # hiccup through the re-assert path and fails closed
        reads = iter([999, None, None, None, None, None, None, None])
        monkeypatch.setattr(bridge, "_active_window_id",
                            lambda: next(reads, None))
        monkeypatch.setattr(bridge, "_FOCUS_SETTLE_S", 0.5)
        monkeypatch.setattr(bridge, "_FOCUS_POLL_STEP_S", 0.01)
        focuses = []
        monkeypatch.setattr(bridge, "focus_window", focuses.append)
        assert bridge._assert_focused(self._window()) is False
        assert len(focuses) == 1  # one re-assert, then fail closed

    def test_unreadable_property_fails_open(self, bridge, monkeypatch):
        # non-EWMH WM / no X server: the assertion cannot run — typing must
        # not brick, and no re-focus is attempted
        monkeypatch.setattr(bridge, "_active_window_id", lambda: None)
        monkeypatch.setattr(bridge, "_FOCUS_SETTLE_S", 0.5)
        monkeypatch.setattr(bridge, "_FOCUS_POLL_STEP_S", 0.01)
        focuses = []
        monkeypatch.setattr(bridge, "focus_window", focuses.append)
        start = time.monotonic()
        assert bridge._assert_focused(self._window()) is True
        elapsed = time.monotonic() - start
        assert focuses == []
        # fast fail-open: two consecutive unreadable reads short-circuit —
        # the full settle budget is never burned (the #492 probe's echo
        # budget depends on this)
        assert elapsed < 0.5

    def test_active_window_id_never_raises(self, monkeypatch):
        # the bridge fixture stubs _active_window_id, so it cannot pin the
        # real function's exception safety — load a fresh module and break
        # the loader underneath the REAL function instead (still hermetic:
        # the raise happens before any display access)
        mod = load_bridge()

        def boom():
            raise RuntimeError("no X here")
        monkeypatch.setattr(mod, "_x11_lib", boom)
        assert mod._active_window_id() is None

    def test_type_stolen_focus_409_no_keystrokes(self, live, monkeypatch):
        bridge, driver, port = live
        monkeypatch.setattr(bridge, "_assert_focused", lambda w: False)
        status, body = req(port, "POST", "/api/type", {"text": "hi"})
        assert status == 409
        assert "focus" in body["error"]
        assert [c for c in driver.calls if c[0] == "type_text"] == []
        # the focus hop itself still happened — loud refusal, not silent
        assert ("bring_to_front", {"pid": 33, "window_id": 303}) in \
            driver.calls

    def test_type_focus_ok_200(self, live, monkeypatch):
        bridge, driver, port = live
        monkeypatch.setattr(bridge, "_assert_focused", lambda w: True)
        status, _ = req(port, "POST", "/api/type", {"text": "hi"})
        assert status == 200
        assert driver.calls[-1][0] == "type_text"

    def test_key_stolen_focus_409_no_keystrokes(self, live, monkeypatch):
        bridge, driver, port = live
        monkeypatch.setattr(bridge, "_assert_focused", lambda w: False)
        status, body = req(port, "POST", "/api/key", {"key": "Enter"})
        assert status == 409
        assert "focus" in body["error"]
        assert [c for c in driver.calls if c[0] == "press_key"] == []


# ---------------------------------------------------------------- cua/bin shell scripts


class TestLiveness:
    """#784: /api/liveness is the keepalive's restart probe — it must answer
    without shelling out to cua-driver, so a slow driver can never
    false-trip the keepalive's 5s curl budget into a spurious restart."""

    def test_liveness_answers_alive(self, live):
        _, _, port = live
        status, body = req(port, "GET", "/api/liveness")
        assert status == 200
        assert body == {"alive": True}

    def test_liveness_never_shells_out(self, live, monkeypatch):
        # The regression this endpoint exists for: /api/status runs
        # `cua-driver status` with a 10s budget, which exceeded the
        # keepalive's 5s liveness curl and restarted a healthy bridge.
        # If liveness ever touches a subprocess — via ANY of the bridge
        # module's spawn paths (subprocess.run, subprocess.Popen,
        # os.system) — or the probe cache lock, fail loudly and instantly.
        bridge, _, port = live

        def _forbidden(*a, **k):
            raise AssertionError(
                "liveness must not spawn a subprocess (keepalive 5s budget)")

        class _ForbiddenLock:
            def __enter__(self):
                raise AssertionError(
                    "liveness must not touch the probe cache")
            def __exit__(self, *a):
                return False

        monkeypatch.setattr(subprocess, "run", _forbidden)
        monkeypatch.setattr(subprocess, "Popen", _forbidden)
        monkeypatch.setattr(os, "system", _forbidden)
        monkeypatch.setattr(bridge, "_probe_lock", _ForbiddenLock())
        status, body = req(port, "GET", "/api/liveness")
        assert status == 200
        assert body == {"alive": True}

    def test_liveness_ignores_query_string(self, live):
        _, _, port = live
        status, body = req(port, "GET", "/api/liveness?probe=1")
        assert status == 200
        assert body == {"alive": True}


class TestShellScripts:
    BIN = os.path.join(CUA_DIR, "bin")

    def _scripts(self):
        return sorted(f for f in os.listdir(self.BIN) if f.endswith(".sh"))

    def test_scripts_exist(self):
        names = self._scripts()
        assert "cua-desktop.sh" in names
        assert "cua-keepalive.sh" in names

    def test_all_scripts_pass_bash_syntax_check(self):
        for name in self._scripts():
            p = subprocess.run(["bash", "-n", os.path.join(self.BIN, name)],
                               capture_output=True, text=True)
            assert p.returncode == 0, f"{name}: {p.stderr}"

    def test_all_scripts_have_shebang(self):
        for name in self._scripts():
            with open(os.path.join(self.BIN, name), "rb") as f:
                first = f.readline()
            assert first.startswith(b"#!"), name
            assert b"bash" in first or b"sh" in first, name

    def test_all_scripts_are_executable(self):
        for name in self._scripts():
            mode = os.stat(os.path.join(self.BIN, name)).st_mode
            assert mode & stat.S_IXUSR, name


# ---------------------------------------------------------------- concurrency + screenshot temp file


class TestBridgeServer:
    def test_server_is_threaded(self, bridge):
        from http.server import ThreadingHTTPServer
        assert issubclass(bridge.BridgeServer, ThreadingHTTPServer)
        assert bridge.BridgeServer.daemon_threads is True

    def test_concurrency_bound_is_sane(self, bridge):
        assert isinstance(bridge.MAX_CONCURRENT_REQUESTS, int)
        # Pin the exact bound: widening 8 -> 16 (or narrowing it) is a
        # deliberate concurrency policy change, not a tune-by-feel tweak,
        # so it must edit this assertion, not slip through a range check.
        assert bridge.MAX_CONCURRENT_REQUESTS == 8

    def test_concurrent_requests_do_not_serialize(self, live, monkeypatch):
        # A slow driver call must not head-of-line-block a second request:
        # two parallel /api/windows with a 0.5s driver stall should finish
        # in well under 1.0s on the threaded server.
        import time
        bridge, driver, port = live

        def slow_call(tool, args):
            if tool == "list_windows":
                time.sleep(0.5)
            return FakeDriver(WINDOWS)(tool, args)

        monkeypatch.setattr(bridge, "call", slow_call)
        results = []
        start = time.monotonic()

        def one():
            results.append(req(port, "GET", "/api/windows"))

        threads = [threading.Thread(target=one) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(10)
        elapsed = time.monotonic() - start
        assert len(results) == 2
        assert all(s == 200 for s, _ in results), results
        assert elapsed < 0.95, f"requests serialized: {elapsed:.2f}s"

    def test_concurrency_bound_enforced(self, live, monkeypatch):
        # The headline claim of BridgeServer: no more than
        # MAX_CONCURRENT_REQUESTS handler bodies execute at once. 16
        # parallel slow requests must never peak above the bound — the
        # test fails if the semaphore is removed or weakened (peak would
        # hit 16), and the peak > 1 guard proves the bound is exercised
        # rather than the requests merely serializing.
        import time
        bridge, driver, port = live
        active = 0
        peak = 0
        lock = threading.Lock()

        def slow_call(tool, args):
            nonlocal active, peak
            if tool == "list_windows":
                with lock:
                    active += 1
                    peak = max(peak, active)
                try:
                    time.sleep(0.5)
                finally:
                    with lock:
                        active -= 1
            return FakeDriver(WINDOWS)(tool, args)

        monkeypatch.setattr(bridge, "call", slow_call)
        threads = [threading.Thread(target=lambda: req(port, "GET", "/api/windows"))
                   for _ in range(16)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(30)
        assert peak <= bridge.MAX_CONCURRENT_REQUESTS, f"peak={peak}"
        # and the bound is actually doing something (not trivially true)
        assert peak > 1, f"peak={peak} — requests serialized, bound untested"


class TestScreenshotTempFile:
    def _raw_get(self, port, path):
        conn = HTTPConnection("127.0.0.1", port, timeout=10)
        conn.request("GET", path, headers={"X-CUA": "1"})
        resp = conn.getresponse()
        data = resp.read()
        conn.close()
        return resp.status, data

    def test_screenshot_uses_private_tempfile(self, live, monkeypatch):
        import tempfile
        bridge, driver, port = live
        seen_paths = []

        def fake_call(tool, args):
            if tool == "get_desktop_state":
                out = args["screenshot_out_file"]
                seen_paths.append(out)
                with open(out, "wb") as f:
                    f.write(b"\x89PNG-fake")
                return {"ok": True}
            return FakeDriver(WINDOWS)(tool, args)

        monkeypatch.setattr(bridge, "call", fake_call)
        status, body = self._raw_get(port, "/api/screenshot")
        assert status == 200
        assert len(seen_paths) == 1
        out = seen_paths[0]
        assert out != "/tmp/cua-bridge-shot.png"
        assert os.path.dirname(out) == tempfile.gettempdir()
        # private (0600) at creation and unlinked after serving
        assert not os.path.exists(out)

    def test_screenshot_paths_are_unique_per_request(
            self, live, monkeypatch):
        bridge, driver, port = live
        seen_paths = []

        def fake_call(tool, args):
            if tool == "get_desktop_state":
                seen_paths.append(args["screenshot_out_file"])
                with open(args["screenshot_out_file"], "wb") as f:
                    f.write(b"x")
                return {"ok": True}
            return FakeDriver(WINDOWS)(tool, args)

        monkeypatch.setattr(bridge, "call", fake_call)
        assert self._raw_get(port, "/api/screenshot")[0] == 200
        assert self._raw_get(port, "/api/screenshot")[0] == 200
        assert seen_paths[0] != seen_paths[1]

    def test_screenshot_tempfile_is_0600(self, live, monkeypatch):
        import stat as statmod
        bridge, driver, port = live
        modes = []

        def fake_call(tool, args):
            if tool == "get_desktop_state":
                out = args["screenshot_out_file"]
                modes.append(statmod.S_IMODE(os.stat(out).st_mode))
                with open(out, "wb") as f:
                    f.write(b"x")
                return {"ok": True}
            return FakeDriver(WINDOWS)(tool, args)

        monkeypatch.setattr(bridge, "call", fake_call)
        assert self._raw_get(port, "/api/screenshot")[0] == 200
        assert modes == [0o600], modes


# ------------------------------------------------- #493 env-file trust


def _write_env_file(path, content="export DISPLAY=:98\nexport DBUS_SESSION_BUS_ADDRESS=unix:x\n", mode=0o600):
    with open(path, "w") as f:
        f.write(content)
    os.chmod(path, mode)
    return path


class TestEnvFileTrust:
    def test_trusted_file_is_accepted(self, bridge, tmp_path):
        p = _write_env_file(str(tmp_path / "env"))
        assert bridge._env_file_trusted(p) is True

    def test_missing_file_is_untrusted(self, bridge, tmp_path):
        assert bridge._env_file_trusted(str(tmp_path / "nope")) is False

    def test_group_writable_is_untrusted(self, bridge, tmp_path):
        p = _write_env_file(str(tmp_path / "env"), mode=0o620)
        assert bridge._env_file_trusted(p) is False

    def test_other_writable_is_untrusted(self, bridge, tmp_path):
        p = _write_env_file(str(tmp_path / "env"), mode=0o606)
        assert bridge._env_file_trusted(p) is False

    def test_group_readable_but_not_writable_is_trusted(self, bridge, tmp_path):
        p = _write_env_file(str(tmp_path / "env"), mode=0o640)
        assert bridge._env_file_trusted(p) is True

    def test_symlink_is_untrusted_even_to_trusted_target(
            self, bridge, tmp_path):
        target = _write_env_file(str(tmp_path / "real"))
        link = str(tmp_path / "link")
        os.symlink(target, link)
        # the swap vector: follows the link (exists) but the link itself
        # is untrusted
        assert os.path.exists(link)
        assert bridge._env_file_trusted(link) is False

    def test_directory_is_untrusted(self, bridge, tmp_path):
        assert bridge._env_file_trusted(str(tmp_path)) is False

    def test_other_owner_is_untrusted(self, bridge, tmp_path, monkeypatch):
        p = _write_env_file(str(tmp_path / "env"))
        # owned by the real euid; pretend we run as someone else
        real_euid = os.geteuid()
        monkeypatch.setattr(bridge.os, "geteuid", lambda: real_euid + 999999)
        assert bridge._env_file_trusted(p) is False

    def test_env_open_is_single_syscall_with_no_follow(
            self, bridge, tmp_path, monkeypatch):
        # the check and the open must be one syscall: O_NOFOLLOW on the
        # open whose fd the validation reads from, so a planted symlink
        # cannot be swapped in between check and parse (#493 TOCTOU)
        p = _write_env_file(str(tmp_path / "env"))
        seen = {}
        real_open = os.open

        def spy_open(path, flags, *args):
            seen["flags"] = flags
            return real_open(path, flags, *args)

        monkeypatch.setattr(bridge.os, "open", spy_open)
        assert bridge._env_file_trusted(p) is True
        assert "flags" in seen, "validation never opened the file"
        assert seen["flags"] & os.O_NOFOLLOW, \
            "env file opened without O_NOFOLLOW"


class TestLoadSandboxEnv:
    def test_parses_trusted_env_file(self, bridge, tmp_path, monkeypatch):
        p = _write_env_file(str(tmp_path / "env"),
                            "export DISPLAY=:98\nexport CUA_TEST_MARKER=hello\n")
        monkeypatch.setattr(bridge, "ENV_FILE", p)
        env = bridge._load_sandbox_env()
        assert env["DISPLAY"] == ":98"
        assert env["CUA_TEST_MARKER"] == "hello"

    def test_ignores_untrusted_env_file(self, bridge, tmp_path, monkeypatch,
                                        capsys):
        p = _write_env_file(str(tmp_path / "env"),
                            "export CUA_TEST_MARKER=evil\n", mode=0o666)
        monkeypatch.setattr(bridge, "ENV_FILE", p)
        env = bridge._load_sandbox_env()
        # fail-safe: the hostile content never enters the environment
        assert "CUA_TEST_MARKER" not in env
        # ... and the skip is loud, not silent
        assert "untrusted" in capsys.readouterr().err

    def test_ignores_symlinked_env_file(self, bridge, tmp_path, monkeypatch,
                                        capsys):
        target = _write_env_file(str(tmp_path / "real"),
                                 "export CUA_TEST_MARKER=evil\n")
        link = str(tmp_path / "env")
        os.symlink(target, link)
        monkeypatch.setattr(bridge, "ENV_FILE", link)
        env = bridge._load_sandbox_env()
        assert "CUA_TEST_MARKER" not in env
        assert "untrusted" in capsys.readouterr().err

    def test_missing_env_file_still_yields_sane_defaults(
            self, bridge, tmp_path, monkeypatch):
        monkeypatch.setattr(bridge, "ENV_FILE", str(tmp_path / "nope"))
        env = bridge._load_sandbox_env()
        assert env["GDK_BACKEND"] == "x11"
        assert env["XDG_SESSION_TYPE"] == "x11"
        assert "WAYLAND_DISPLAY" not in env
        assert env["PATH"].split(os.pathsep)[0].endswith("cua/bin")

    def test_module_base_env_keeps_x11_pins(self, bridge):
        # pins the import-time contract: untrusted env files must not strip
        # the forced backend flags out of BASE_ENV
        assert bridge.BASE_ENV["GDK_BACKEND"] == "x11"
        assert bridge.BASE_ENV["XDG_SESSION_TYPE"] == "x11"
        assert "WAYLAND_DISPLAY" not in bridge.BASE_ENV


# ------------------------------------------------- #495 singleton lock


class TestSingletonLock:
    def test_second_acquire_in_same_process_fails(self, bridge, tmp_path):
        lock = str(tmp_path / "bridge.lock")
        fd = bridge.acquire_singleton_lock(lock)
        assert fd is not None
        # LOCK_NB: the second contender must fail fast, not block
        assert bridge.acquire_singleton_lock(lock) is None

    def test_lock_releases_when_holder_closes(self, bridge, tmp_path):
        lock = str(tmp_path / "bridge.lock")
        fd = bridge.acquire_singleton_lock(lock)
        assert fd is not None
        os.close(fd)
        assert bridge.acquire_singleton_lock(lock) is not None

    def test_cross_process_exclusion(self, bridge, tmp_path):
        lock = str(tmp_path / "bridge.lock")
        # first process holds the lock; it prints "ready" only after the
        # flock is held, so there is no startup race with the assertion
        holder = subprocess.Popen(
            [sys.executable, "-c",
             "import fcntl, os, time; "
             f"fd = os.open({lock!r}, os.O_RDWR | os.O_CREAT, 0o644); "
             "fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB); "
             "import sys; sys.stdout.write('ready'); sys.stdout.flush(); "
             "time.sleep(10)"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        try:
            assert holder.stdout.read(5) == "ready"
            assert bridge.acquire_singleton_lock(lock) is None
        finally:
            holder.terminate()
            holder.wait(timeout=10)
        # after the holder dies the lock is free again — no stale state
        assert bridge.acquire_singleton_lock(lock) is not None

    def test_lock_file_is_created(self, bridge, tmp_path):
        lock = str(tmp_path / "bridge.lock")
        assert not os.path.exists(lock)
        assert bridge.acquire_singleton_lock(lock) is not None
        assert os.path.exists(lock)

    def test_default_lock_lives_in_private_cache(self, bridge):
        # never world-writable /tmp: any local user could squat a /tmp
        # lock and hold the bridge down, or plant a symlink there that
        # the O_CREAT open would follow (#493's sibling)
        assert bridge._SINGLETON_LOCK_FILE == os.path.join(
            bridge._HOME, ".cache", "cua-bridge.lock")
        assert not bridge._SINGLETON_LOCK_FILE.startswith("/tmp/")

    def test_lock_open_failure_is_loud(self, bridge, tmp_path, capsys):
        # an unopenable lock (here: the parent path is a regular file, so
        # the makedirs fails) must exit 1 with a message — never a silent
        # skip that leaves the bridge unprotected
        blocker = tmp_path / "blocker"
        blocker.write_text("x")
        with pytest.raises(SystemExit) as e:
            bridge.acquire_singleton_lock(str(blocker / "bridge.lock"))
        assert e.value.code == 1
        assert "cannot open singleton lock" in capsys.readouterr().err


# ------------------------------------------------- #491 launch registry


class FakePopen:
    """Popen stand-in: records argv, returns a chosen pid."""

    instances = []

    def __init__(self, argv, **kw):
        self.argv = argv
        self.kw = kw
        self.pid = kw.pop("_pid", 999001)
        FakePopen.instances.append(self)


def _child_states(monkeypatch, bridge, states):
    """Stub process liveness: states maps pid -> "running" | "zombie";
    missing pids are dead. waitpid(WNOHANG) reaps zombies (like the real
    thing — a second waitpid on a reaped pid raises ChildProcessError);
    kill(pid, 0) probes existence."""
    def fake_waitpid(pid, options):
        st = states.get(pid)
        if st == "running":
            return (0, 0)
        if st == "zombie":
            states[pid] = None  # reaped
            return (pid, 0)
        raise ChildProcessError(10, "No child processes")

    def fake_kill(pid, sig):
        if sig == 0 and states.get(pid) in ("running", "zombie"):
            return None
        raise OSError(3, "No such process")

    monkeypatch.setattr(bridge.os, "waitpid", fake_waitpid)
    monkeypatch.setattr(bridge.os, "kill", fake_kill)


def _alive_kill(monkeypatch, bridge, live_pids):
    """waitpid/kill stub: pids in live_pids are running, all else dead."""
    _child_states(monkeypatch, bridge, {p: "running" for p in live_pids})


class TestLaunchRegistry:
    APP = {"demo": [sys.executable, "-c", "pass"]}

    def _bridge(self, bridge, monkeypatch, live_pids=(999001,)):
        monkeypatch.setattr(bridge, "LAUNCH_ALLOWLIST", dict(self.APP))
        monkeypatch.setattr(bridge.shutil, "which", lambda p: p)
        monkeypatch.setattr(bridge.subprocess, "Popen", FakePopen)
        _alive_kill(monkeypatch, bridge, set(live_pids))

    def test_launch_records_pid_in_registry(self, bridge, monkeypatch):
        self._bridge(bridge, monkeypatch)
        before = bridge.time.time()
        assert bridge.launch_app("demo") == {"launched": "demo"}
        insts = bridge.launched_instances("demo")
        assert len(insts) == 1
        assert insts[0]["pid"] == 999001
        assert before <= insts[0]["launched_at"] <= bridge.time.time()

    def test_dead_pids_are_pruned_on_read(self, bridge, monkeypatch):
        self._bridge(bridge, monkeypatch, live_pids=())
        bridge.launch_app("demo")
        # the spawn recorded a pid, but nothing is alive -> pruned
        assert bridge.launched_instances("demo") == []
        assert bridge.all_launched() == {}

    def test_prune_keeps_live_and_drops_dead(self, bridge, monkeypatch):
        self._bridge(bridge, monkeypatch, live_pids={100, 300})

        def popen_seq(argv, **kw):
            return FakePopen(argv, **dict(kw, _pid=popen_seq.next()))

        popen_seq.next = iter([100, 200, 300]).__next__
        monkeypatch.setattr(bridge.subprocess, "Popen", popen_seq)
        for _ in range(3):
            bridge.launch_app("demo")
        insts = bridge.launched_instances("demo")
        assert [i["pid"] for i in insts] == [100, 300]

    def test_unknown_app_still_rejected(self, bridge, monkeypatch):
        # the allowlist rules regardless of the singleton flag
        self._bridge(bridge, monkeypatch)
        with pytest.raises(ValueError, match="not allowlisted"):
            bridge.launch_app("evil-app")

    def _live_launch(self, bridge, monkeypatch, live_pids, popen_pid=4242):
        """Stub the spawn path for endpoint tests: allowlisted demo app,
        counting fake Popen, controllable liveness."""
        monkeypatch.setattr(bridge, "LAUNCH_ALLOWLIST", dict(self.APP))
        monkeypatch.setattr(bridge.shutil, "which", lambda p: p)
        calls = []

        def fake_popen(argv, **kw):
            calls.append(argv)
            return SimpleNamespace(pid=popen_pid)

        monkeypatch.setattr(bridge.subprocess, "Popen", fake_popen)
        _alive_kill(monkeypatch, bridge, set(live_pids))
        return calls

    def test_singleton_second_launch_409(self, live, monkeypatch):
        bridge, driver, port = live
        calls = self._live_launch(bridge, monkeypatch, live_pids={4242})
        status, body = req(port, "POST", "/api/launch",
                           {"app": "demo", "singleton": True})
        assert status == 200
        status, body = req(port, "POST", "/api/launch",
                           {"app": "demo", "singleton": True})
        assert status == 409
        assert body["error"] == "already running"
        assert body["pids"] == [4242]
        assert len(calls) == 1  # the refused launch never spawned

    def test_singleton_allows_relaunch_after_death(self, live, monkeypatch):
        bridge, driver, port = live
        calls = self._live_launch(bridge, monkeypatch, live_pids=set())
        status, _ = req(port, "POST", "/api/launch",
                        {"app": "demo", "singleton": True})
        assert status == 200
        # the recorded pid is dead, so the guard prunes it and spawns again
        status, _ = req(port, "POST", "/api/launch",
                        {"app": "demo", "singleton": True})
        assert status == 200
        assert len(calls) == 2

    def test_singleton_string_false_does_not_opt_in(self, live, monkeypatch):
        # only a literal JSON true opts in — a "false" string is a normal
        # multi-launch, not a silent singleton refusal
        bridge, driver, port = live
        calls = self._live_launch(bridge, monkeypatch, live_pids={4242})
        for _ in range(2):
            status, _ = req(port, "POST", "/api/launch",
                            {"app": "demo", "singleton": "false"})
            assert status == 200
        assert len(calls) == 2

    def test_singleton_race_spawns_exactly_once(self, live, monkeypatch):
        # the panel double-tap, the exact failure mode #491 exists to fix:
        # two threads racing through the real handler must yield one spawn
        bridge, driver, port = live
        calls = self._live_launch(bridge, monkeypatch, live_pids={4242})
        results = []

        def one():
            results.append(req(port, "POST", "/api/launch",
                               {"app": "demo", "singleton": True}))

        threads = [threading.Thread(target=one) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(10)
        assert sorted(s for s, _ in results) == [200, 409]
        assert len(calls) == 1
        loser = [b for s, b in results if s == 409][0]
        assert loser["pids"] == [4242]

    def test_registry_survives_reload(self, bridge, monkeypatch):
        self._bridge(bridge, monkeypatch, live_pids={555})
        monkeypatch.setattr(
            bridge.subprocess, "Popen",
            lambda argv, **kw: SimpleNamespace(pid=555))
        bridge.launch_app("demo")
        assert os.path.exists(bridge._LAUNCH_REGISTRY_FILE)
        # simulate a bridge restart: wipe memory, reload from disk
        bridge._LAUNCHED.clear()
        bridge._load_launched()
        insts = bridge.launched_instances("demo")
        assert [i["pid"] for i in insts] == [555]

    def test_reload_prunes_dead_pids(self, bridge, monkeypatch):
        self._bridge(bridge, monkeypatch, live_pids=set())
        with open(bridge._LAUNCH_REGISTRY_FILE, "w") as f:
            json.dump({"demo": [{"pid": 111, "launched_at": 1.0},
                                {"pid": 222, "launched_at": 2.0}]}, f)
        bridge._load_launched()
        assert bridge.launched_instances("demo") == []

    def test_reload_ignores_corrupt_file(self, bridge, monkeypatch):
        self._bridge(bridge, monkeypatch)
        with open(bridge._LAUNCH_REGISTRY_FILE, "w") as f:
            f.write("not json{{{")
        bridge._load_launched()  # must not raise
        assert bridge.all_launched() == {}

    def test_reload_ignores_wrong_shape(self, bridge, monkeypatch):
        self._bridge(bridge, monkeypatch)
        with open(bridge._LAUNCH_REGISTRY_FILE, "w") as f:
            json.dump({"demo": [{"pid": "not-an-int", "launched_at": 1.0},
                                {"nope": True}], "bad": 42}, f)
        bridge._load_launched()
        assert bridge.all_launched() == {}

    def test_valid_registry_pid(self, bridge):
        v = bridge._valid_registry_pid
        assert v(4242) is True
        assert v(1) is False        # init: _is_alive(1) never prunes
        assert v(0) is False       # special to waitpid()/kill()
        assert v(-5) is False
        assert v(True) is False   # bool is int in Python (== 1)
        assert v(False) is False
        assert v("4242") is False
        assert v(4242.0) is False
        assert v(None) is False

    def test_reload_rejects_special_and_non_pids(self, bridge, monkeypatch):
        # A persisted {"pid": 0} (or True == 1 == init, or a literal 1)
        # would never prune: _is_alive(0) reports alive whenever the
        # process group is non-empty (and _is_alive(1) likewise, since
        # kill(1, 0) succeeds), so the singleton guard would 409
        # "already running" forever. They must be dropped at load, not
        # kept as entries.
        self._bridge(bridge, monkeypatch)
        monkeypatch.setattr(bridge, "_is_alive", lambda pid: True)
        with open(bridge._LAUNCH_REGISTRY_FILE, "w") as f:
            json.dump({"demo": [{"pid": 0, "launched_at": 1.0},
                                {"pid": True, "launched_at": 1.0},
                                {"pid": 1, "launched_at": 1.0},
                                {"pid": -5, "launched_at": 1.0},
                                {"pid": 555, "launched_at": 1.0}]}, f)
        bridge._load_launched()
        assert [i["pid"] for i in bridge.launched_instances("demo")] == [555]

    def test_save_never_follows_planted_symlink(self, bridge, monkeypatch,
                                                tmp_path):
        # A planted symlink at the tmp path must never be followed: the
        # exclusive create refuses it, the path is unlinked, and a real
        # file is created instead — the decoy target is untouched.
        self._bridge(bridge, monkeypatch)
        decoy = tmp_path / "decoy.json"
        decoy.write_text("DECOY")
        tmp = bridge._LAUNCH_REGISTRY_FILE + ".tmp"
        os.symlink(decoy, tmp)
        bridge._LAUNCHED["demo"] = [{"pid": 555, "launched_at": 1.0}]
        with bridge._LAUNCHED_LOCK:
            bridge._save_launched_locked()
        assert decoy.read_text() == "DECOY"
        assert not os.path.islink(bridge._LAUNCH_REGISTRY_FILE)
        with open(bridge._LAUNCH_REGISTRY_FILE) as f:
            assert json.load(f)["demo"][0]["pid"] == 555

    def test_save_replaces_stale_tmp(self, bridge, monkeypatch):
        # A stale tmp file from a crashed save must not block the next
        # one: it is dropped and re-created exclusively.
        self._bridge(bridge, monkeypatch)
        tmp = bridge._LAUNCH_REGISTRY_FILE + ".tmp"
        with open(tmp, "w") as f:
            f.write("stale")
        bridge._LAUNCHED["demo"] = [{"pid": 555, "launched_at": 1.0}]
        with bridge._LAUNCHED_LOCK:
            bridge._save_launched_locked()
        assert not os.path.exists(tmp)  # renamed into place
        with open(bridge._LAUNCH_REGISTRY_FILE) as f:
            assert json.load(f)["demo"][0]["pid"] == 555

    def test_registry_file_is_owner_only(self, bridge, monkeypatch):
        # The tmp file is created 0600, and os.replace preserves it —
        # group/other must never gain bits, regardless of umask.
        self._bridge(bridge, monkeypatch)
        bridge._LAUNCHED["demo"] = [{"pid": 555, "launched_at": 1.0}]
        with bridge._LAUNCHED_LOCK:
            bridge._save_launched_locked()
        mode = os.stat(bridge._LAUNCH_REGISTRY_FILE).st_mode
        assert stat.S_IMODE(mode) & 0o077 == 0, oct(mode)

    def test_zombie_is_reaped_and_pruned(self, bridge, monkeypatch):
        # Security review finding: launch_app drops the Popen handle
        # without wait(), so an exited app is a zombie — and kill(pid, 0)
        # succeeds on zombies. Without the waitpid reap, the entry would
        # never prune and singleton would 409 "already running" forever.
        states = {4242: "zombie"}
        _child_states(monkeypatch, bridge, states)
        monkeypatch.setattr(bridge, "LAUNCH_ALLOWLIST", dict(self.APP))
        monkeypatch.setattr(bridge.shutil, "which", lambda p: p)
        monkeypatch.setattr(bridge.subprocess, "Popen",
                            lambda argv, **kw: SimpleNamespace(pid=4242))
        bridge.launch_app("demo")
        assert bridge.launched_instances("demo") == []
        assert states[4242] is None  # reaped, not left a zombie

    def test_singleton_launch_after_app_exit(self, live, monkeypatch):
        # the regression: once the app exits, a singleton launch must
        # spawn fresh instead of 409ing forever on the zombie
        bridge, driver, port = live
        states = {4242: "running"}
        _child_states(monkeypatch, bridge, states)
        monkeypatch.setattr(bridge, "LAUNCH_ALLOWLIST", dict(self.APP))
        monkeypatch.setattr(bridge.shutil, "which", lambda p: p)
        calls = []

        def fake_popen(argv, **kw):
            calls.append(argv)
            return SimpleNamespace(pid=4242)

        monkeypatch.setattr(bridge.subprocess, "Popen", fake_popen)
        assert req(port, "POST", "/api/launch",
                   {"app": "demo", "singleton": True})[0] == 200
        states[4242] = "zombie"  # the app exits
        assert req(port, "POST", "/api/launch",
                   {"app": "demo", "singleton": True})[0] == 200
        assert len(calls) == 2

    def test_default_launch_still_spawns_duplicates(self, live, monkeypatch):
        # no "singleton" flag -> the old behavior: spawn again, no refusal
        bridge, driver, port = live
        spawned = []
        monkeypatch.setattr(
            bridge, "launch_app",
            lambda name, singleton=False:
                spawned.append(name) or {"launched": name})
        for _ in range(2):
            status, _ = req(port, "POST", "/api/launch", {"app": "xterm"})
            assert status == 200
        assert spawned == ["xterm", "xterm"]

    def test_status_exposes_launched_set(self, live, monkeypatch):
        bridge, driver, port = live
        monkeypatch.setattr(bridge, "LAUNCH_ALLOWLIST", dict(self.APP))
        monkeypatch.setattr(bridge.shutil, "which", lambda p: p)
        _alive_kill(monkeypatch, bridge, {777})
        monkeypatch.setattr(
            bridge.subprocess, "Popen",
            lambda argv, **kw: FakePopen(argv, **dict(kw, _pid=777)))
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **k: SimpleNamespace(returncode=0, stdout="ok\n",
                                           stderr=""))
        bridge.launch_app("demo")
        # hermetic: the real probe spawns xev — stub it, assert it rides along
        monkeypatch.setattr(bridge, "get_input_liveness",
                            lambda run_probe=False: ("unknown", "stubbed",
                                                     None))
        status, body = req(port, "GET", "/api/status")
        assert status == 200
        assert list(body["launched"]) == ["demo"]
        assert body["launched"]["demo"][0]["pid"] == 777
        assert body["input"]["state"] == "unknown"

    def test_status_launched_prunes_dead(self, live, monkeypatch):
        bridge, driver, port = live
        monkeypatch.setattr(bridge, "LAUNCH_ALLOWLIST", dict(self.APP))
        monkeypatch.setattr(bridge.shutil, "which", lambda p: p)
        monkeypatch.setattr(bridge.subprocess, "Popen", FakePopen)
        _alive_kill(monkeypatch, bridge, set())  # nothing alive
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **k: SimpleNamespace(returncode=0, stdout="ok\n",
                                           stderr=""))
        bridge.launch_app("demo")
        # hermetic: the real probe spawns xev — stub it, assert it rides along
        monkeypatch.setattr(bridge, "get_input_liveness",
                            lambda run_probe=False: ("unknown", "stubbed",
                                                     None))
        status, body = req(port, "GET", "/api/status")
        assert status == 200
        assert body["launched"] == {}
        assert body["input"]["state"] == "unknown"


# ------------------------------------------------- #492 input-path liveness probe


XEV_WINDOW = {"pid": 4242, "window_id": 505, "app_name": "xev",
              "title": "Event Tester", "is_on_screen": True, "z_index": 3,
              "bounds": {"x": 100, "y": 100, "width": 200, "height": 200}}
# A hostile X client can set any title it likes: this window looks like
# xev (and wins the z-order) but is not our child — the probe must select
# by PID, never by title.
SPOOF_WINDOW = {"pid": 9999, "window_id": 909, "app_name": "spoofer",
                "title": "Event Tester", "is_on_screen": True, "z_index": 9,
                "bounds": {"x": 0, "y": 0, "width": 200, "height": 200}}


class FakeXevProc:
    """Stands in for the xev child process: stdout is a real OS pipe the
    test pre-fills, so the probe's select/os.read loop runs for real."""

    def __init__(self, argv, out_chunks=(), eof=True):
        self.argv = argv
        self.killed = False
        self._w = None
        r, w = os.pipe()
        for chunk in out_chunks:
            os.write(w, chunk)
        if eof:
            os.close(w)
        else:
            self._w = w  # held open: reads block until the probe's deadline
        self._stdout = os.fdopen(r, "rb", buffering=0)

    @property
    def stdout(self):
        return self._stdout

    @property
    def pid(self):
        return 4242

    def kill(self):
        self.killed = True

    def wait(self, timeout=None):
        try:
            self._stdout.close()
        except OSError:
            pass
        if self._w is not None:
            os.close(self._w)
            self._w = None
        return 0


class RejectingDriver(FakeDriver):
    """Fails the global input key the way a driver without the untargeted
    route would — the probe must report "unknown", never "wedged"."""

    def __call__(self, tool, args):
        self.calls.append((tool, args))
        if tool == "press_key" and "pid" not in args:
            raise RuntimeError("press_key needs a target window")
        if tool == "list_windows":
            return {"windows": self.windows}
        return {"ok": True}


class AppearingDriver(FakeDriver):
    """list_windows gains the xev window only after the first call — models
    reality, where the probe's pre-spawn focus capture cannot see xev."""

    def __call__(self, tool, args):
        self.calls.append((tool, args))
        if tool == "list_windows":
            if not getattr(self, "_seen", False):
                self._seen = True
                return {"windows": self.windows}
            return {"windows": self.windows + [XEV_WINDOW]}
        return {"ok": True}


class LateDriver(FakeDriver):
    """The xev window appears near the end of the probe budget — the echo
    wait gets ~zero budget, which is inconclusive, not a wedge."""

    def __init__(self, windows, appear_after):
        super().__init__(windows)
        self._t0 = time.monotonic()
        self._appear_after = appear_after

    def __call__(self, tool, args):
        self.calls.append((tool, args))
        if tool == "list_windows":
            if time.monotonic() - self._t0 >= self._appear_after:
                return {"windows": self.windows + [XEV_WINDOW]}
            return {"windows": self.windows}
        return {"ok": True}


class TestInputLiveness:
    def _patch_binaries(self, bridge, monkeypatch, xev=True, stdbuf=True):
        def which(p, path=None):
            if p == "xev":
                return "/usr/bin/xev" if xev else None
            if p == "stdbuf":
                return "/usr/bin/stdbuf" if stdbuf else None
            return None
        monkeypatch.setattr(bridge.shutil, "which", which)

    def _patch_popen(self, bridge, monkeypatch, spawned, **proc_kw):
        def fake_popen(argv, **kw):
            proc = FakeXevProc(argv, **proc_kw)
            spawned.append(proc)
            return proc
        monkeypatch.setattr(bridge.subprocess, "Popen", fake_popen)

    def test_probe_ok_on_keypress_echo(self, bridge, monkeypatch):
        self._patch_binaries(bridge, monkeypatch)
        spawned = []
        self._patch_popen(
            bridge, monkeypatch, spawned,
            out_chunks=(b"KeyPress event, serial 34, synthetic NO\n",))
        driver = AppearingDriver(WINDOWS)
        monkeypatch.setattr(bridge, "call", driver)
        state, detail = bridge._input_probe(timeout=2.0)
        assert state == "ok"
        assert "KeyPress" in detail
        # the xev child is always reaped
        assert spawned and spawned[0].killed
        # fixed argv, no shell: stdbuf line-buffers xev's stdout; both
        # binaries resolved against the bridge's own PATH (absolute)
        argv = spawned[0].argv
        assert argv[0] == "/usr/bin/stdbuf"
        assert any(a.endswith("/xev") for a in argv)
        assert "-event" in argv and "keyboard" in argv
        # the probe key goes out untargeted (the XTEST global route) after
        # the xev window is focused; the pre-probe focus is restored after
        brings = [c[1] for c in driver.calls if c[0] == "bring_to_front"]
        assert brings[0] == {"pid": 4242, "window_id": 505}
        assert brings[-1] == {"pid": 33, "window_id": 303}  # chromium back
        key = [c[1] for c in driver.calls if c[0] == "press_key"][0]
        assert key == {"key": "Shift_L", "modifiers": [],
                       "delivery_mode": "foreground"}
        assert "pid" not in key and "window_id" not in key

    def test_probe_selects_window_by_pid_not_title(
            self, bridge, monkeypatch):
        # the spoof outranks xev on z-order and title — the probe must still
        # focus OUR xev (pid 4242), never the spoof
        self._patch_binaries(bridge, monkeypatch)
        spawned = []
        self._patch_popen(
            bridge, monkeypatch, spawned,
            out_chunks=(b"KeyPress event, serial 34\n",))
        driver = FakeDriver(WINDOWS + [SPOOF_WINDOW, XEV_WINDOW])
        monkeypatch.setattr(bridge, "call", driver)
        state, _ = bridge._input_probe(timeout=2.0)
        assert state == "ok"
        brings = [c[1] for c in driver.calls if c[0] == "bring_to_front"]
        assert brings[0] == {"pid": 4242, "window_id": 505}

    def test_probe_unknown_when_pid_match_missing(
            self, bridge, monkeypatch):
        # only the spoof is present: no PID match is inconclusive — a
        # spoofed title must never manufacture a "wedged" verdict
        self._patch_binaries(bridge, monkeypatch)
        spawned = []
        self._patch_popen(bridge, monkeypatch, spawned)
        monkeypatch.setattr(bridge, "call",
                            FakeDriver(WINDOWS + [SPOOF_WINDOW]))
        state, detail = bridge._input_probe(timeout=0.5)
        assert state == "unknown"
        assert "4242" in detail  # names the pid it looked for
        assert spawned[0].killed

    def test_probe_skips_malformed_xev_window(self, bridge, monkeypatch,
                                              capsys):
        # #1580: the probe's window pick must go through the same #1575
        # shape filter the other handlers use. Here the only pid-4242
        # window is malformed (string z_index) — the probe cannot trust
        # the order-comparison, so the window reads as no-PID-match:
        # "unknown" (inconclusive), never a wedge. The malformed window
        # is logged like every other filtered window.
        self._patch_binaries(bridge, monkeypatch)
        spawned = []
        self._patch_popen(bridge, monkeypatch, spawned,
                          out_chunks=(b"KeyPress event, serial 34\n",))
        bad_xev = dict(XEV_WINDOW)
        bad_xev["z_index"] = "high"
        monkeypatch.setattr(bridge, "call", FakeDriver([bad_xev]))
        state, detail = bridge._input_probe(timeout=0.5)
        assert state == "unknown"
        assert "never appeared" in detail
        assert "malformed window" in capsys.readouterr().err

    def test_probe_malformed_decoy_does_not_win_window_pick(self, bridge,
                                                            monkeypatch):
        # #1580: a malformed pid-4242 decoy outranking the real xev on
        # z-order must be filtered before the pick — the probe focuses
        # the well-formed xev window, not the decoy. Pre-fix the decoy
        # won max() and focus_window's w["window_id"] KeyError'd,
        # surfacing as a probe error instead of "ok".
        self._patch_binaries(bridge, monkeypatch)
        spawned = []
        self._patch_popen(bridge, monkeypatch, spawned,
                          out_chunks=(b"KeyPress event, serial 34\n",))
        decoy = dict(XEV_WINDOW)
        decoy["z_index"] = 9
        del decoy["window_id"]  # malformed: probe indexes w["window_id"]
        driver = FakeDriver([decoy, XEV_WINDOW])
        monkeypatch.setattr(bridge, "call", driver)
        state, _ = bridge._input_probe(timeout=2.0)
        assert state == "ok"
        brings = [c[1] for c in driver.calls
                  if c[0] == "bring_to_front"]
        assert brings[0] == {"pid": 4242, "window_id": 505}

    def test_probe_wedged_on_echo_deadline(self, bridge, monkeypatch):
        self._patch_binaries(bridge, monkeypatch)
        spawned = []
        self._patch_popen(bridge, monkeypatch, spawned, eof=False)
        monkeypatch.setattr(bridge, "call", FakeDriver(WINDOWS + [XEV_WINDOW]))
        start = time.monotonic()
        state, detail = bridge._input_probe(timeout=1.0)
        elapsed = time.monotonic() - start
        assert state == "wedged"
        assert "wedged" in detail
        assert 0.9 <= elapsed < 2.0  # a full echo observation happened
        assert spawned[0].killed

    def test_probe_unknown_when_window_appears_too_late(
            self, bridge, monkeypatch):
        # the window appears with ~no budget left for the echo wait: zero
        # observation is inconclusive, never "wedged"
        self._patch_binaries(bridge, monkeypatch)
        spawned = []
        self._patch_popen(bridge, monkeypatch, spawned, eof=False)
        monkeypatch.setattr(bridge, "call", LateDriver(WINDOWS, 0.6))
        state, detail = bridge._input_probe(timeout=1.0)
        assert state == "unknown"
        assert "too late" in detail
        assert spawned[0].killed

    def test_probe_unknown_when_xev_exits_silent(self, bridge, monkeypatch):
        # xev dying tells us nothing about the XTEST device: a probe
        # failure, not wedge evidence
        self._patch_binaries(bridge, monkeypatch)
        spawned = []
        self._patch_popen(bridge, monkeypatch, spawned)  # immediate EOF
        monkeypatch.setattr(bridge, "call", FakeDriver(WINDOWS + [XEV_WINDOW]))
        state, detail = bridge._input_probe(timeout=2.0)
        assert state == "unknown"
        assert "exited before echoing" in detail
        assert spawned[0].killed

    def test_probe_unknown_without_xev(self, bridge, monkeypatch):
        self._patch_binaries(bridge, monkeypatch, xev=False)
        spawned = []
        self._patch_popen(bridge, monkeypatch, spawned)
        monkeypatch.setattr(bridge, "call", FakeDriver(WINDOWS + [XEV_WINDOW]))
        state, detail = bridge._input_probe(timeout=1.0)
        assert state == "unknown"
        assert "xev" in detail
        assert not spawned  # nothing spawned when the probe cannot run

    def test_probe_unknown_without_stdbuf(self, bridge, monkeypatch):
        self._patch_binaries(bridge, monkeypatch, stdbuf=False)
        spawned = []
        self._patch_popen(bridge, monkeypatch, spawned)
        monkeypatch.setattr(bridge, "call", FakeDriver(WINDOWS + [XEV_WINDOW]))
        state, detail = bridge._input_probe(timeout=1.0)
        assert state == "unknown"
        assert "stdbuf" in detail
        assert not spawned

    def test_probe_unknown_when_driver_rejects_global_key(
            self, bridge, monkeypatch):
        # a probe failure is never reported as a wedge (fail-safe direction)
        self._patch_binaries(bridge, monkeypatch)
        spawned = []
        self._patch_popen(
            bridge, monkeypatch, spawned,
            out_chunks=(b"KeyPress event, serial 34\n",))
        monkeypatch.setattr(bridge, "call",
                            RejectingDriver(WINDOWS + [XEV_WINDOW]))
        state, _ = bridge._input_probe(timeout=2.0)
        assert state == "unknown"
        assert spawned[0].killed

    def test_probe_unknown_on_driver_error(self, bridge, monkeypatch):
        self._patch_binaries(bridge, monkeypatch)
        spawned = []
        self._patch_popen(bridge, monkeypatch, spawned)

        def bad_call(tool, args):
            raise RuntimeError("driver exploded")
        monkeypatch.setattr(bridge, "call", bad_call)
        state, _ = bridge._input_probe(timeout=1.0)
        assert state == "unknown"
        assert spawned[0].killed

    def test_probe_cancel_skips_side_effects(self, bridge, monkeypatch):
        self._patch_binaries(bridge, monkeypatch)
        spawned = []
        self._patch_popen(bridge, monkeypatch, spawned)
        driver = FakeDriver(WINDOWS + [XEV_WINDOW])
        monkeypatch.setattr(bridge, "call", driver)
        cancel = threading.Event()
        cancel.set()  # budget already blown before the probe starts
        state, _ = bridge._input_probe(timeout=2.0, cancel=cancel)
        assert state == "unknown"
        assert not spawned  # not even spawned
        assert driver.calls == []  # no focus hop, no key

    def test_probe_stolen_focus_is_unknown_not_wedged(
            self, bridge, monkeypatch):
        # #494: focus stolen between the probe's focus hop and the XTEST
        # key — the missing echo must not false-report a wedge, and the
        # key must not be sent into the wrong window
        self._patch_binaries(bridge, monkeypatch)
        spawned = []
        self._patch_popen(bridge, monkeypatch, spawned,
                          out_chunks=(b"KeyPress event, serial 34\n",))
        driver = AppearingDriver(WINDOWS)
        monkeypatch.setattr(bridge, "call", driver)
        monkeypatch.setattr(bridge, "_active_window_id", lambda: 999)
        monkeypatch.setattr(bridge, "_FOCUS_SETTLE_S", 0.05)
        monkeypatch.setattr(bridge, "_FOCUS_POLL_STEP_S", 0.01)
        state, detail = bridge._input_probe(timeout=2.0)
        assert state == "unknown"
        assert "focus" in detail
        assert [c for c in driver.calls if c[0] == "press_key"] == []
        assert spawned[0].killed  # xev still reaped

    def test_bounded_probe_passes_through(self, bridge, monkeypatch):
        monkeypatch.setattr(bridge, "_input_probe",
                            lambda timeout, cancel: ("ok", "echo in 0.1s"))
        assert bridge._bounded_probe() == ("ok", "echo in 0.1s")

    def test_bounded_probe_budget_overrun_is_unknown(
            self, bridge, monkeypatch):
        def slow_probe(timeout, cancel):
            time.sleep(5)
            return ("ok", "too late")
        monkeypatch.setattr(bridge, "_input_probe", slow_probe)
        start = time.monotonic()
        state, detail = bridge._bounded_probe(timeout=0.2)
        elapsed = time.monotonic() - start
        assert state == "unknown"
        assert "budget" in detail
        assert elapsed < 2  # the status handler is never held hostage

    def _reset_cache(self, bridge, monkeypatch):
        monkeypatch.setattr(bridge, "_probe_cache",
                            {"state": "unknown", "detail": "d0",
                             "checked_at": None})
        monkeypatch.setattr(bridge, "_probe_inflight", False)

    def test_get_input_liveness_serves_cache(self, bridge, monkeypatch):
        self._reset_cache(bridge, monkeypatch)

        def spy():
            raise AssertionError("probe must not run")
        monkeypatch.setattr(bridge, "_bounded_probe", spy)
        assert bridge.get_input_liveness(
            run_probe=False) == ("unknown", "d0", None)

    def test_get_input_liveness_single_flight(self, bridge, monkeypatch):
        self._reset_cache(bridge, monkeypatch)
        monkeypatch.setattr(bridge, "_probe_inflight", True)

        def spy():
            raise AssertionError("second probe must not start")
        monkeypatch.setattr(bridge, "_bounded_probe", spy)
        # a probe is already running: serve the stale cache, don't pile on
        assert bridge.get_input_liveness(
            run_probe=True) == ("unknown", "d0", None)

    def test_get_input_liveness_runs_and_caches(self, bridge, monkeypatch):
        self._reset_cache(bridge, monkeypatch)
        monkeypatch.setattr(bridge, "_bounded_probe",
                            lambda: ("ok", "fresh echo"))
        state, detail, checked_at = bridge.get_input_liveness(run_probe=True)
        assert state == "ok" and detail == "fresh echo"
        assert abs(checked_at - time.time()) < 5
        # the outcome is cached for plain reads
        assert bridge.get_input_liveness(
            run_probe=False) == ("ok", "fresh echo", checked_at)

    def test_status_probe_param_runs_probe(self, live, monkeypatch):
        bridge, _, port = live
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **k: SimpleNamespace(returncode=0, stdout="ok\n",
                                           stderr=""))
        seen = {}
        monkeypatch.setattr(
            bridge, "get_input_liveness",
            lambda run_probe=False: seen.update(run_probe=run_probe)
            or ("wedged", "fake wedge", 1700000000.0))
        status, body = req(port, "GET", "/api/status?probe=1")
        assert status == 200
        assert seen == {"run_probe": True}
        assert body["input"] == {"state": "wedged", "detail": "fake wedge",
                                 "checked_at": 1700000000.0,
                                 "driver": "cua-driver 0.28.2"}

    def test_status_without_probe_param_is_read_only(self, live, monkeypatch):
        bridge, _, port = live
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **k: SimpleNamespace(returncode=0, stdout="ok\n",
                                           stderr=""))
        seen = {}
        monkeypatch.setattr(
            bridge, "get_input_liveness",
            lambda run_probe=False: seen.update(run_probe=run_probe)
            or ("unknown", "cached", None))
        status, body = req(port, "GET", "/api/status")
        assert status == 200
        assert seen == {"run_probe": False}
        assert body["input"]["state"] == "unknown"

    def test_status_input_unknown_when_driver_down(self, live, monkeypatch):
        bridge, _, port = live
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **k: SimpleNamespace(returncode=1, stdout="",
                                           stderr="boom"))

        def spy(run_probe=False):
            raise AssertionError("no probe when the driver is down")
        monkeypatch.setattr(bridge, "get_input_liveness", spy)
        status, body = req(port, "GET", "/api/status?probe=1")
        assert status == 200
        assert body["ok"] is False
        assert body["input"] == {
            "state": "unknown",
            "detail": "driver down — input probe skipped",
            "checked_at": None, "driver": "cua-driver 0.28.2"}


# ---------------------------------------------------------------- hardening response headers (#1228)


class TestHardeningHeaders:
    """Issue #1228: the bridge is API-only (JSON through the _json choke
    point plus the one /api/screenshot PNG), so X-Content-Type-Options:
    nosniff is the hardening header that matters here — nothing is
    framed, so X-Frame-Options is not needed. Every wire response must
    carry nosniff; deleting it must fail."""

    def _raw(self, port, method, path):
        conn = HTTPConnection("127.0.0.1", port, timeout=10)
        conn.request(method, path, headers={"X-CUA": "1"})
        resp = conn.getresponse()
        data = resp.read()
        headers = {k.lower(): v for k, v in resp.getheaders()}
        conn.close()
        return resp.status, headers, data

    def test_json_responses_carry_nosniff(self, live):
        bridge, driver, port = live
        # GET success, GET 404, and a POST 404 — all leave through _json.
        cases = [("GET", "/api/liveness", 200),
                 ("GET", "/api/windows", 200),
                 ("GET", "/no/such/route", 404),
                 ("POST", "/no/such/route", 404)]
        for method, path, want in cases:
            status, headers, _ = self._raw(port, method, path)
            assert status == want, (method, path)
            assert headers.get("x-content-type-options") == "nosniff", \
                (method, path)

    def test_screenshot_png_carries_nosniff(self, live, monkeypatch):
        bridge, driver, port = live

        def fake_call(tool, args):
            if tool == "get_desktop_state":
                with open(args["screenshot_out_file"], "wb") as f:
                    f.write(b"\x89PNG-fake")
                return {"ok": True}
            return FakeDriver(WINDOWS)(tool, args)

        monkeypatch.setattr(bridge, "call", fake_call)
        status, headers, _ = self._raw(port, "GET", "/api/screenshot")
        assert status == 200
        assert headers.get("x-content-type-options") == "nosniff"


# ---------------------------------------------------------------- audit sink shape (#1588)


class TestAuditSink:
    """Issue #1588 (D-CBA-4): the bridge owns its audit sink — O_APPEND|
    O_NOFOLLOW open at 0600, size-capped rotation with a bounded number of
    generations, and a one-line-per-event contract the S1/S2 writers will
    use. These tests drive _RotatingBridgeLog directly (never install() on
    the module-global — install dup2's the test process's own fds)."""

    def _log(self, bridge, tmp_path, **kw):
        kw.setdefault("max_bytes", 400)
        kw.setdefault("generations", 2)
        return bridge._RotatingBridgeLog(
            path=str(tmp_path / "cua-bridge.log"), **kw)

    def _open_fd(self, log):
        fd = log._open()
        assert fd is not None
        log._fd = fd
        return log

    def test_open_creates_0600(self, bridge, tmp_path):
        log = self._log(bridge, tmp_path)
        fd = log._open()
        assert fd is not None
        os.close(fd)
        mode = stat.S_IMODE(os.stat(str(tmp_path / "cua-bridge.log")).st_mode)
        assert mode == 0o600

    def test_open_tightens_legacy_0644(self, bridge, tmp_path):
        # A log written before #1588 under a default umask must not stay
        # world-readable while naming window titles.
        p = tmp_path / "cua-bridge.log"
        p.write_text("legacy line\n")
        os.chmod(p, 0o644)
        log = self._log(bridge, tmp_path)
        fd = log._open()
        assert fd is not None
        os.close(fd)
        mode = stat.S_IMODE(os.stat(str(p)).st_mode)
        assert mode == 0o600
        assert p.read_text() == "legacy line\n"  # content preserved

    def test_open_refuses_symlink(self, bridge, tmp_path, capsys):
        target = tmp_path / "victim.log"
        target.write_text("do not touch\n")
        link = tmp_path / "cua-bridge.log"
        os.symlink(target, link)
        log = self._log(bridge, tmp_path)
        assert log._open() is None  # refused, not followed
        assert "symlink" in capsys.readouterr().err
        assert target.read_text() == "do not touch\n"

    def test_event_format_is_one_line(self, bridge, tmp_path):
        log = self._open_fd(self._log(bridge, tmp_path))
        line = bridge._format_bridge_event(
            "csrf-reject",
            "bad-host\nINJECTED\rline \\ backslash\x0bVT\x0cFF\u2028\u2029\x1bESC")
        assert log.write_line(line)
        os.close(log._fd)
        lines = (tmp_path / "cua-bridge.log").read_text().splitlines()
        assert len(lines) == 1  # the hostile line-breaks never became lines
        assert "INJECTED" in lines[0] and "\\n" in lines[0]
        assert "\\r" in lines[0] and "\\\\" in lines[0]
        assert "\\u000b" in lines[0] and "\\u000c" in lines[0]
        assert "\\u2028" in lines[0] and "\\u2029" in lines[0]
        assert "\\u001b" in lines[0]
        assert " level=WARNING " in lines[0]
        assert " kind=csrf-reject " in lines[0]
        assert lines[0].startswith("ts=") and " msg=" in lines[0]

    def test_bad_kind_and_level_rejected(self, bridge):
        for bad_kind in ("", "has space", "new\nline", "semi;colon",
                         "x" * 65, None):
            try:
                bridge._format_bridge_event(bad_kind, "m")
            except ValueError:
                pass
            else:
                raise AssertionError(f"kind {bad_kind!r} not rejected")
        try:
            bridge._format_bridge_event("ok-kind", "m", level="INFO")
        except ValueError:
            pass
        else:
            raise AssertionError("level INFO not rejected")

    def test_rotation_caps_size_and_generations(self, bridge, tmp_path):
        log = self._open_fd(self._log(bridge, tmp_path, max_bytes=300,
                                      generations=2))
        for i in range(40):
            line = bridge._format_bridge_event("evt", f"payload-{i:02d}")
            assert log.write_line(line)
        os.close(log._fd)
        base = tmp_path / "cua-bridge.log"
        # At most <cap> + one line in the live file; exactly 2 rotated
        # generations; nothing beyond .2 — total disk bounded.
        assert os.path.getsize(base) < 300 + 200
        assert (tmp_path / "cua-bridge.log.1").exists()
        assert (tmp_path / "cua-bridge.log.2").exists()
        assert not (tmp_path / "cua-bridge.log.3").exists()
        total = sum(p.stat().st_size for p in tmp_path.iterdir())
        assert total < 3 * (300 + 200)

    def test_install_rotates_oversized_existing_log(self, bridge, tmp_path):
        # A log that outgrew the cap while the bridge was down rotates at
        # the next install — but install() dup2's the test process's own
        # fds 1/2, so save and restore them around the call.
        p = tmp_path / "cua-bridge.log"
        p.write_text("x" * 5000)
        log = self._log(bridge, tmp_path, max_bytes=300, generations=2)
        save1, save2 = os.dup(1), os.dup(2)
        try:
            assert log.install()
            assert log.installed
            # fd 1 now points at the (fresh) log — the dup2 landed.
            assert os.fstat(1).st_ino == os.stat(str(p)).st_ino
        finally:
            os.dup2(save1, 1)
            os.dup2(save2, 2)
            os.close(save1)
            os.close(save2)
            os.close(log._fd)
            log._fd = None
        assert (tmp_path / "cua-bridge.log.1").exists()
        assert os.path.getsize(p) < 300

    def test_write_line_false_when_uninstalled(self, bridge):
        log = bridge._RotatingBridgeLog(path="/nonexistent-dir/x.log")
        assert log.write_line("ts=1 level=WARNING kind=k msg=m\n") is False

    def test_log_bridge_event_falls_back_to_stderr(self, bridge, tmp_path,
                                                   monkeypatch, capsys):
        # The module-global sink is never installed in tests; the choke
        # point must still emit — to plain stderr — never drop.
        monkeypatch.setattr(bridge, "_BRIDGE_LOG",
                            bridge._RotatingBridgeLog(
                                path=str(tmp_path / "never-installed.log")))
        bridge.log_bridge_event("probe-reject", "missing-csrf-header")
        err = capsys.readouterr().err
        assert "kind=probe-reject" in err
        assert "missing-csrf-header" in err
        assert not (tmp_path / "never-installed.log").exists()

    def test_event_parse_round_trip(self, bridge):
        # The contract's parse rule (BLOCKING-1): structured fields are
        # four fixed-order tokens, msg is everything after "msg=" to
        # end-of-line. A hostile msg with spaces, "=", the literal
        # " msg=", every splitlines() boundary char, and backslashes must
        # round-trip exactly.
        hostile = ("a b=c msg= INJECTED\nline\r\\ tail\x0b\x0c\u2028\u2029"
                   "\x1b\x85")
        line = bridge._format_bridge_event("evt-1", hostile, level="ERROR")
        parsed = bridge._parse_bridge_event(line)
        assert parsed == {"ts": parsed["ts"], "level": "ERROR",
                          "kind": "evt-1", "msg": hostile}
        assert isinstance(parsed["ts"], int)

    def test_parse_rejects_non_contract_lines(self, bridge):
        # Skip rule: legacy free-form diagnostics do not start with "ts="
        # and must be rejected, never parsed.
        for bad in ("cua-bridge: WARNING: something happened\n",
                    "ts=abc level=WARNING kind=k msg=m\n",
                    "ts=1 level=INFO kind=k msg=m\n",
                    "ts=1 level=WARNING kind=bad kind msg=m\n",
                    "ts=1 level=WARNING kind=k\n",
                    "level=WARNING kind=k msg=m\n",
                    ""):
            try:
                bridge._parse_bridge_event(bad)
            except ValueError:
                pass
            else:
                raise AssertionError(f"line not rejected: {bad!r}")

    def test_write_line_recovers_after_rotation_open_failure(
            self, bridge, tmp_path, monkeypatch):
        # BLOCKING-2: a rotation whose reopen fails must not wedge the
        # sink permanently — one reopen attempt per write recovers it.
        log = self._open_fd(self._log(bridge, tmp_path, max_bytes=200,
                                      generations=1))
        log._install_attempted = True  # as install() would set
        real_open_quiet = log._open_quiet
        monkeypatch.setattr(log, "_open_quiet", lambda: None)
        for i in range(20):
            log.write_line(bridge._format_bridge_event("evt", f"p{i}"))
        assert log._fd is None  # sink down, the BLOCKING-2 scenario
        monkeypatch.setattr(log, "_open_quiet", real_open_quiet)
        # The recovery path dup2's the test process's own fds 1/2 —
        # save and restore them around the call.
        save1, save2 = os.dup(1), os.dup(2)
        try:
            assert log.write_line(
                bridge._format_bridge_event("evt", "recovered"))
            assert log._fd is not None
        finally:
            os.dup2(save1, 1)
            os.dup2(save2, 2)
            os.close(save1)
            os.close(save2)
        os.close(log._fd)
        log._fd = None
        assert "msg=recovered" in (tmp_path / "cua-bridge.log").read_text()

    def test_never_installed_sink_does_not_open_files(
            self, bridge, tmp_path, monkeypatch, capsys):
        # A sink that was never installed keeps the plain-stderr fallback
        # — write_line must not open the log path behind the caller's
        # back (the _install_attempted gate).
        monkeypatch.setattr(bridge, "_BRIDGE_LOG",
                            bridge._RotatingBridgeLog(
                                path=str(tmp_path / "never-installed.log")))
        bridge.log_bridge_event("k", "v")
        assert "kind=k" in capsys.readouterr().err
        assert not (tmp_path / "never-installed.log").exists()


# ------------------------------------------------- #1586 S1 / #1587 S2
# The bridge owned its audit sink since #1588, but wrote nothing into it
# from the request path: unhandled 500s left no server-side trace
# (F-CBA-2, #1586) and CSRF/host refusals were invisible on the box
# (F-CBA-3, #1587). These tests pin the S1/S2 writers — kind vocabulary,
# content rules (D-CBA-1/D-CBA-2), and the S2 volume bound.


class TestObservabilityS1S2:
    def _capture_events(self, bridge, monkeypatch):
        captured = []

        def recorder(kind, msg, level="WARNING"):
            captured.append({"kind": kind, "msg": msg, "level": level})

        monkeypatch.setattr(bridge, "log_bridge_event", recorder)
        bridge._reset_csrf_refusal_state()
        return captured

    # -- S1: unhandled 500s -------------------------------------------------

    def _boom(self, tool, args):
        # call() wraps opaque driver stderr in RuntimeError — that stderr
        # can echo the text the driver failed to inject, so the audit
        # line must name the class, never this text.
        raise RuntimeError("driver stderr: failed to type 'hunter2-typed'")

    def test_get_500_writes_http_500_audit_line(self, live, monkeypatch):
        bridge, _, port = live
        captured = self._capture_events(bridge, monkeypatch)
        monkeypatch.setattr(bridge, "call", self._boom)
        status, body = req(port, "GET", "/api/windows")
        # Client contract unchanged: truncated exception text, 500.
        assert status == 500
        assert body == {"error": "driver stderr: failed to type "
                                 "'hunter2-typed'"}
        assert len(captured) == 1
        evt = captured[0]
        assert evt["kind"] == "http-500"
        assert evt["level"] == "ERROR"
        assert "RuntimeError" in evt["msg"]
        assert "hunter2-typed" not in evt["msg"]  # D-CBA-1
        assert "\n" not in evt["msg"]  # D-CBA-2: one line
        assert ".py:" in evt["msg"]  # condensed frame summary

    def test_post_500_writes_http_500_audit_line(self, live, monkeypatch):
        bridge, _, port = live
        captured = self._capture_events(bridge, monkeypatch)
        monkeypatch.setattr(bridge, "call", self._boom)
        status, body = req(port, "POST", "/api/click",
                           {"x": 50, "y": 50, "button": "left"})
        assert status == 500
        assert body["error"].startswith("driver stderr:")
        assert len(captured) == 1
        assert captured[0]["kind"] == "http-500"
        assert captured[0]["level"] == "ERROR"
        assert "hunter2-typed" not in captured[0]["msg"]

    def test_http_500_label_never_carries_exception_text(self, bridge):
        try:
            raise RuntimeError("opaque blob: hunter2-typed")
        except RuntimeError as e:
            label = bridge._http_500_label(e)
        assert label.startswith("RuntimeError ")
        assert "hunter2-typed" not in label
        assert ".py:" in label  # deepest frame location
        assert "\n" not in label and len(label) <= 200

    def test_http_500_label_without_traceback(self, bridge):
        # An exception that was never raised has no __traceback__ —
        # the label degrades to the bare class name, never crashes.
        label = bridge._http_500_label(RuntimeError("x"))
        assert label == "RuntimeError"

    def test_s1_s2_kinds_pass_the_real_formatter_vocabulary(
            self, bridge, capsys):
        # Composition pin (QA): the S1/S2 tests monkeypatch
        # log_bridge_event, so the (kind, level) pairs the writers use
        # would never meet the real _format_bridge_event vocabulary.
        # If _AUDIT_LEVELS ever dropped "ERROR", the S1 line would raise
        # ValueError INSIDE the do_GET/do_POST except handler and abort
        # the 500 response — this test catches that drift.
        bridge.log_bridge_event("http-500", "RuntimeError x", level="ERROR")
        bridge.log_bridge_event("csrf-refusal", "refusal: reason=bad-host")
        err = capsys.readouterr().err
        assert "level=ERROR kind=http-500" in err
        assert "level=WARNING kind=csrf-refusal" in err

    # -- S2: csrf-refusal audit ------------------------------------------------

    def test_csrf_refusal_logs_full_line_first_time(self, live, monkeypatch):
        bridge, _, port = live
        captured = self._capture_events(bridge, monkeypatch)
        status, body = req(port, "POST", "/api/click", {"x": 1, "y": 1},
                           headers={"X-CUA": REMOVE})
        # Refusal contract unchanged: bare 403, no server detail.
        assert status == 403
        assert body == {"error": "forbidden"}
        assert len(captured) == 1
        evt = captured[0]
        assert evt["kind"] == "csrf-refusal"
        assert evt["level"] == "WARNING"
        assert "reason=missing-csrf-header" in evt["msg"]
        assert "src=127.0.0.1" in evt["msg"]

    def test_csrf_refusal_reason_never_carries_header_value(
            self, live, monkeypatch):
        bridge, _, port = live
        captured = self._capture_events(bridge, monkeypatch)
        status, _ = req(port, "POST", "/api/click", {"x": 1, "y": 1},
                        headers={"Host": "evil.example"})
        assert status == 403
        assert len(captured) == 1
        assert "reason=bad-host" in captured[0]["msg"]
        assert "evil.example" not in captured[0]["msg"]  # D-CBA-1

    def test_csrf_refusal_volume_bounding(self, bridge, monkeypatch):
        # 120 refusals must not emit 120 lines: full line + summaries at
        # 10, 100 — then silence again. Routed through the recorder so
        # the real-sink stderr fallback stays quiet during the suite.
        captured = self._capture_events(bridge, monkeypatch)
        emitted = [bridge.record_csrf_refusal("bad-host") for _ in range(120)]
        assert sum(emitted) == 3  # n=1 full, n=10 summary, n=100 summary
        assert emitted[0] == 1 and emitted[9] == 1 and emitted[99] == 1
        assert all(e == 0 for i, e in enumerate(emitted)
                   if i not in (0, 9, 99))
        assert len(captured) == 3
        assert "reason=bad-host" in captured[0]["msg"]
        assert "count=10" in captured[1]["msg"]
        assert "count=100" in captured[2]["msg"]
        assert bridge._csrf_refusal_state["counts"] == {"bad-host": 120}

    def test_csrf_refusal_reason_classes_are_independent(self, bridge,
                                                         monkeypatch):
        captured = self._capture_events(bridge, monkeypatch)
        assert bridge.record_csrf_refusal("bad-host") == 1
        assert bridge.record_csrf_refusal("missing-csrf-header") == 1
        assert len(captured) == 2
        assert "reason=bad-host" in captured[0]["msg"]
        assert "reason=missing-csrf-header" in captured[1]["msg"]

    def test_csrf_refusal_window_rollover_logs_totals(self, bridge,
                                                      monkeypatch):
        captured = self._capture_events(bridge, monkeypatch)
        assert bridge.record_csrf_refusal("bad-host") == 1
        assert bridge.record_csrf_refusal("bad-host") == 0
        assert len(captured) == 1  # only the first full line so far
        real_monotonic = bridge.time.monotonic
        monkeypatch.setattr(bridge.time, "monotonic",
                            lambda: real_monotonic() + 400)
        # Rollover: the old window's totals first, then the new window's
        # first refusal as a fresh full line.
        assert bridge.record_csrf_refusal("bad-host") == 2
        assert "window summary" in captured[1]["msg"]
        assert "bad-host=2" in captured[1]["msg"]
        assert "reason=bad-host" in captured[2]["msg"]
        assert bridge._csrf_refusal_state["counts"] == {"bad-host": 1}

    def test_csrf_refusal_never_raises_on_broken_clock(self, bridge,
                                                       monkeypatch):
        monkeypatch.setattr(bridge.time, "monotonic",
                            lambda: (_ for _ in ()).throw(OSError("clock")))
        assert bridge.record_csrf_refusal("bad-host") == 0  # 403 still out

    def test_csrf_refusal_reason_matrix(self, bridge):
        # _csrf_ok's gate semantics are unchanged by the reason-class
        # refactor: every old False maps to a reason, every old True to
        # None.
        cases = [
            (("GET", {"Host": "127.0.0.1:18731"}, "/"), None),
            (("POST", {"Host": "127.0.0.1:18731"}, "/"), "missing-csrf-header"),
            (("POST", {"Host": "127.0.0.1:18731", "X-CUA": "1"}, "/"), None),
            (("PUT", {"Host": "127.0.0.1:18731"}, "/"),
             "missing-csrf-header"),
            (("PUT", {"Host": "127.0.0.1:18731", "X-CUA": "1"}, "/"), None),
            (("GET", {"Host": "evil.example"}, "/"), "bad-host"),
            (("POST", {"Host": "evil.example", "X-CUA": "1"}, "/"),
             "bad-host"),
            (("GET", {"Host": "127.0.0.1:18731"}, "/api/status"), None),
            (("GET", {"Host": "127.0.0.1:18731"}, "/api/status?probe=1"),
             "missing-csrf-header"),
            (("GET", {"Host": "127.0.0.1:18731", "X-CUA": "1"},
              "/api/status?probe=1"), None),
        ]
        for (command, headers, path), want in cases:
            h = fake_handler(bridge, command, headers, path)
            assert h._csrf_refusal_reason() == want, (command, headers, path)
            assert h._csrf_ok() == (want is None)
