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
"""
import importlib.util
import io
import json
import os
import stat
import subprocess
import sys
import threading
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
def bridge():
    return load_bridge()


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


def fake_handler(bridge, command="GET", headers=None):
    h = bridge.Handler.__new__(bridge.Handler)
    h.command = command
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
        status, body = req(port, "GET", "/api/status")
        assert status == 200
        assert body == {"ok": True, "detail": "ok"}

    def test_get_windows(self, live):
        bridge, driver, port = live
        status, body = req(port, "GET", "/api/windows")
        assert status == 200
        assert len(body["windows"]) == 4

    def test_unknown_path_404(self, live):
        _, _, port = live
        status, body = req(port, "GET", "/nope")
        assert status == 404

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
                            lambda name: {"launched": name})
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


# ---------------------------------------------------------------- cua/bin shell scripts


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
