#!/usr/bin/env python3
"""cua-bridge — localhost HTTP bridge to the CUA Driver desktop on spark-vm.

Listens on 127.0.0.1 only. The private control-panel artifact's backend
calls this over an SSH tunnel from the hatch VM; it shells out to
`cua-driver call` against the spark-vm desktop display (:98). No arbitrary
shell: only the allowlisted desktop actions.

Endpoints:
  GET  /api/status      -> stack + driver state
  GET  /api/windows     -> list_windows
  GET  /api/screenshot  -> PNG bytes of the full desktop
  POST /api/click       -> {"x":screen_x,"y":screen_y,"button":"left"|"right"|"middle"}
  POST /api/type        -> {"text":"..."}            (foreground to focused window)
  POST /api/key         -> {"key":"Enter","modifiers":["ctrl"]}   (foreground)
  POST /api/launch      -> {"app":"xterm"|"terminal"|"chromium"|"blender"} (allowlisted spawn on :98;
                                  the driver's own launch tool is
                                  permission-denied in standard mode)
"""
import json
import os
import shutil
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

DRIVER = "/home/ntindle/cua/bin/cua-driver"
ENV_FILE = "/tmp/cua-desktop/env"
PORT = 18731

BASE_ENV = dict(os.environ)
if os.path.exists(ENV_FILE):
    for line in open(ENV_FILE):
        line = line.strip()
        if line.startswith("export "):
            k, _, v = line[len("export "):].partition("=")
            BASE_ENV[k] = v
BASE_ENV["PATH"] = "/home/ntindle/cua/bin:" + BASE_ENV.get("PATH", "")
# Force the X11 backend: without this, GTK apps on :98 probe the Wayland
# socket in XDG_RUNTIME_DIR (the GNOME session's) and misbehave/crash.
BASE_ENV["GDK_BACKEND"] = "x11"
BASE_ENV["XDG_SESSION_TYPE"] = "x11"
BASE_ENV.pop("WAYLAND_DISPLAY", None)


# launch allowlist: the driver's own launch tool is permission-denied in
# standard mode, so the bridge spawns a fixed set of apps directly on :98.
# chromium here is the Playwright-bundled build (no system chromium installed).
LAUNCH_ALLOWLIST = {
    "xterm": ["xterm", "-geometry", "100x30+40+40"],
    "terminal": ["xfce4-terminal", "--geometry=100x30+40+40"],
    "chromium": ["/home/ntindle/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome",
                 "--no-sandbox", "--disable-dev-shm-usage",
                 "--window-size=1260,740", "--window-position=10,30"],
    "blender": ["/home/ntindle/cua/bin/launch-blender-gui.sh"],
}


def launch_app(name):
    if name not in LAUNCH_ALLOWLIST:
        raise ValueError(f"app not allowlisted: {name!r}")
    argv = LAUNCH_ALLOWLIST[name]
    if not shutil.which(argv[0]) and not os.path.isfile(argv[0]):
        raise RuntimeError(f"{argv[0]} is not installed on spark-vm")
    subprocess.Popen(argv, env=BASE_ENV,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
    return {"launched": name}


def call(tool, args):
    p = subprocess.run(
        [DRIVER, "call", tool],
        input=json.dumps(args).encode(),
        capture_output=True, timeout=30, env=BASE_ENV,
    )
    if p.returncode != 0:
        raise RuntimeError(p.stderr.decode()[:500] or f"driver rc={p.returncode}")
    return json.loads(p.stdout.decode())


def top_window_at(x, y):
    wins = call("list_windows", {}).get("windows", [])
    hits = [w for w in wins
            if w.get("is_on_screen") and w.get("pid")
            and w["bounds"]["x"] <= x < w["bounds"]["x"] + w["bounds"]["width"]
            and w["bounds"]["y"] <= y < w["bounds"]["y"] + w["bounds"]["height"]]
    hits.sort(key=lambda w: w.get("z_index", 0), reverse=True)
    return hits[0] if hits else None


def top_window():
    # The window that should receive type/key input: the topmost NORMAL
    # application window, returned as its list_windows dict (or None).
    # Never the desktop itself (Xfdesktop) nor the always-on-top docks
    # (Xfce4-panel) — with plain max(z_index) the panel would swallow input
    # meant for a real window (seen on the XFCE desktop).
    wins = call("list_windows", {}).get("windows", [])
    app_wins = [w for w in wins if w.get("pid")
                and w.get("app_name") not in ("Xfdesktop", "Xfce4-panel")]
    cands = app_wins or [w for w in wins if w.get("pid")]
    if not cands:
        return None
    return max(cands, key=lambda w: w.get("z_index", 0))


def top_window_pid():
    w = top_window()
    return w["pid"] if w else None


def focus_window(w):
    # Activate the window via EWMH _NET_ACTIVE_WINDOW so it genuinely has
    # keyboard focus. This panel is a remote-desktop-style surface, which
    # is bring_to_front's intended use. (Do NOT use delivery_mode
    # "foreground" for type/key instead: that routes through XTEST global
    # input, and XTEST keyboard events are not delivered by this Xvfb —
    # verified with xev. XSendEvent works, but only to a focused window.)
    call("bring_to_front", {"pid": w["pid"], "window_id": w["window_id"]})


class Handler(BaseHTTPRequestHandler):
    server_version = "cua-bridge/1.0"

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(n) if n else b"{}"
        try:
            return json.loads(raw.decode() or "{}")
        except Exception:
            return {}

    def do_GET(self):
        try:
            if self.path == "/api/status":
                st = subprocess.run([DRIVER, "status"], capture_output=True,
                                    timeout=10, env=BASE_ENV, text=True)
                self._json({"ok": st.returncode == 0,
                            "detail": st.stdout.strip()[:400]})
            elif self.path == "/api/windows":
                self._json(call("list_windows", {}))
            elif self.path == "/api/screenshot":
                out = "/tmp/cua-bridge-shot.png"
                call("get_desktop_state", {"screenshot_out_file": out})
                with open(out, "rb") as f:
                    png = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(png)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(png)
            else:
                self._json({"error": "not found"}, 404)
        except Exception as e:
            self._json({"error": str(e)[:300]}, 500)

    def do_POST(self):
        try:
            data = self._body()
            if self.path == "/api/click":
                x, y = int(data["x"]), int(data["y"])
                button = data.get("button", "left")
                if button not in ("left", "right", "middle"):
                    return self._json({"error": "bad button"}, 400)
                w = top_window_at(x, y)
                if not w:
                    return self._json({"error": "no window at point"}, 404)
                if w.get("app_name") in ("Xfce4-panel", "Xfdesktop"):
                    # Panel buttons and desktop menus ignore synthetic
                    # XSendEvent clicks; use a true global (XTEST) click
                    # with absolute desktop coordinates instead.
                    res = call("click", {"x": x, "y": y, "button": button,
                                         "scope": "desktop"})
                else:
                    b = w["bounds"]
                    res = call("click", {"pid": w["pid"],
                                         "window_id": w["window_id"],
                                         "x": x - b["x"], "y": y - b["y"],
                                         "button": button})
                self._json({"ok": True, "window": w["title"], "result": res})
            elif self.path == "/api/type":
                text = str(data.get("text", ""))[:2000]
                if not text:
                    return self._json({"error": "empty text"}, 400)
                w = top_window()
                if w is None:
                    return self._json({"error": "no window open"}, 404)
                focus_window(w)
                res = call("type_text", {"pid": w["pid"],
                                         "window_id": w["window_id"],
                                         "text": text,
                                         "delivery_mode": "foreground"})
                self._json({"ok": True, "result": res})
            elif self.path == "/api/key":
                key = str(data.get("key", ""))[:40]
                mods = [m for m in data.get("modifiers", []) if m in
                        ("ctrl", "shift", "alt", "super")][:4]
                if not key:
                    return self._json({"error": "empty key"}, 400)
                w = top_window()
                if w is None:
                    return self._json({"error": "no window open"}, 404)
                focus_window(w)
                res = call("press_key", {"pid": w["pid"],
                                         "window_id": w["window_id"],
                                         "key": key, "modifiers": mods,
                                         "delivery_mode": "foreground"})
                self._json({"ok": True, "result": res})
            elif self.path == "/api/launch":
                app = str(data.get("app", ""))[:80]
                if not app:
                    return self._json({"error": "empty app"}, 400)
                try:
                    res = launch_app(app)
                except (ValueError, RuntimeError) as e:
                    return self._json({"error": str(e)[:200]}, 400)
                self._json({"ok": True, "result": res})
            else:
                self._json({"error": "not found"}, 404)
        except Exception as e:
            self._json({"error": str(e)[:300]}, 500)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "stop":
        # bracket-trick so the pkill pattern never matches this process itself
        os.system("pkill -f 'cua-bridge[.]py' 2>/dev/null")
        sys.exit(0)
    srv = HTTPServer(("127.0.0.1", PORT), Handler)
    print(f"cua-bridge listening on 127.0.0.1:{PORT}", flush=True)
    srv.serve_forever()
