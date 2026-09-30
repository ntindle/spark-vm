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
                                  permission-denied in standard mode).
                                  Optional "singleton": true refuses (409)
                                  while a bridge-launched instance is still
                                  alive; GET /api/status exposes the running
                                  set under "launched" (#491).
"""
import fcntl
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_HOME = os.path.expanduser("~")
DRIVER = os.path.join(_HOME, "cua/bin/cua-driver")
ENV_FILE = "/tmp/cua-desktop/env"
PORT = 18731
# CSRF hardening: the bridge binds localhost only, but a browser on the
# user's own machine can reach it through their SSH tunnel — exactly what
# a malicious web page would abuse. So (a) reject any request whose Host
# header is not this bridge's own address, and (b) require a custom header
# on all state-changing requests: browsers must preflight those, and we
# never answer with permissive CORS.
# 18732 is the local end of the operator SSH tunnel (127.0.0.1:18732 -> 127.0.0.1:18731); loopback-only too.
ALLOWED_HOSTS = {"127.0.0.1:18731", "localhost:18731", "127.0.0.1:18732", "localhost:18732"}
CSRF_HEADER = "X-CUA"
CSRF_VALUE = "1"

def _open_trusted_env(path):
    """Open the desktop env file and validate it in one step.

    The file is opened ONCE with O_NOFOLLOW and validated with fstat on
    the resulting fd — the validation and the parse below read from the
    same fd, so there is no check-then-open TOCTOU window in which a
    planted symlink could be swapped in between (#493).
    Returns the open fd (caller closes), or None if the file is missing,
    is a symlink, is not a regular file owned by this user, or is
    group/other-writable.
    """
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError:
        return None  # missing, symlink (ELOOP), or unreadable — all untrusted
    try:
        st = os.fstat(fd)
    except OSError:
        os.close(fd)
        return None
    if (not stat.S_ISREG(st.st_mode)
            or st.st_uid != os.geteuid()
            or st.st_mode & (stat.S_IWGRP | stat.S_IWOTH)):
        os.close(fd)
        return None
    return fd


def _env_file_trusted(path):
    """True if the desktop env file is safe to parse (#493)."""
    fd = _open_trusted_env(path)
    if fd is None:
        return False
    os.close(fd)
    return True


def _load_sandbox_env():
    """Build the subprocess environment: desktop env file merged over the
    ambient environment, then the bridge's forced X11 pins. The env file is
    opened once with O_NOFOLLOW and parsed from that same validated fd —
    an untrusted or missing env file is skipped (with a stderr warning),
    never parsed; the bridge still runs on sane ambient defaults (#493)."""
    env = dict(os.environ)
    if os.path.exists(ENV_FILE):
        fd = _open_trusted_env(ENV_FILE)
        if fd is not None:
            with os.fdopen(fd, "r") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("export "):
                        k, _, v = line[len("export "):].partition("=")
                        env[k] = v
        else:
            print(f"cua-bridge: WARNING: {ENV_FILE} is untrusted "
                  "(symlink/owner/mode) — ignoring it", file=sys.stderr)
    env["PATH"] = os.path.join(_HOME, "cua/bin") + ":" + env.get("PATH", "")
    # Force the X11 backend: without this, GTK apps on :98 probe the Wayland
    # socket in XDG_RUNTIME_DIR (the GNOME session's) and misbehave/crash.
    env["GDK_BACKEND"] = "x11"
    env["XDG_SESSION_TYPE"] = "x11"
    env.pop("WAYLAND_DISPLAY", None)
    return env


BASE_ENV = _load_sandbox_env()


# The singleton lock fds must stay open for the whole process, so they are
# kept here — never GC'd out from under the lock holder (#495).
_singleton_lock_fds = []

# The lock lives in the user's own ~/.cache (never world-writable /tmp:
# any local user could otherwise squat the lock file and hold the bridge
# down, or plant a symlink there — #493's sibling).
_SINGLETON_LOCK_FILE = os.path.join(_HOME, ".cache", "cua-bridge.lock")


def acquire_singleton_lock(path=_SINGLETON_LOCK_FILE):
    """Hold an exclusive flock on the singleton lock for this process's
    lifetime. Returns the fd, or None if another bridge already holds it
    (#495). flock (not a pidfile): the lock releases itself if the process
    dies, so there are no stale-pid races.
    Python's os.open sets CLOEXEC (PEP 446) and subprocess defaults
    close_fds=True, so driver/launcher children never inherit this fd — the
    bridge side cannot jam its own lock the way a shell-held fd can.
    If the lock file itself cannot be opened (missing dir, permissions),
    this exits(1) with a stderr message — lock failure is fatal and loud,
    never a silent skip."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
    except OSError as e:
        print(f"cua-bridge: cannot open singleton lock {path}: {e}",
              file=sys.stderr)
        raise SystemExit(1)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(fd)
        return None
    _singleton_lock_fds.append(fd)
    return fd


# launch allowlist: the driver's own launch tool is permission-denied in
# standard mode, so the bridge spawns a fixed set of apps directly on :98.
# chromium here is the Playwright-bundled build (no system chromium installed).
LAUNCH_ALLOWLIST = {
    "xterm": ["xterm", "-geometry", "100x30+40+40"],
    "terminal": ["xfce4-terminal", "--geometry=100x30+40+40"],
    "chromium": [os.path.join(_HOME, ".cache/ms-playwright/chromium-1234/chrome-linux64/chrome"),
                 "--no-sandbox", "--disable-dev-shm-usage",
                 "--window-size=1260,740", "--window-position=10,30"],
    "blender": [os.path.join(_HOME, "cua/bin/launch-blender-gui.sh")],
}


class AlreadyRunning(Exception):
    """Raised by launch_app(singleton=True) while an instance is alive (#491)."""

    def __init__(self, app, pids):
        super().__init__(f"{app} already running: {pids}")
        self.app = app
        self.pids = pids


def launch_app(name, singleton=False):
    """Spawn an allowlisted app on :98 and record its PID (#491).

    With singleton=True the prune → check → spawn → record sequence runs
    inside ONE _LAUNCHED_LOCK acquisition, so two racing requests (a panel
    double-tap — the exact failure mode this guards) cannot both observe
    an empty registry and both spawn; the loser gets AlreadyRunning,
    which the handler maps to 409. Splitting the check and the spawn
    across two lock acquisitions would reintroduce the race.
    Popen-under-lock is safe here: fork+exec is fast and every handler
    already runs on its own thread."""
    if name not in LAUNCH_ALLOWLIST:
        raise ValueError(f"app not allowlisted: {name!r}")
    argv = LAUNCH_ALLOWLIST[name]
    if not shutil.which(argv[0]) and not os.path.isfile(argv[0]):
        raise RuntimeError(f"{argv[0]} is not installed on spark-vm")
    with _LAUNCHED_LOCK:
        _prune_launched()
        if singleton:
            live = _LAUNCHED.get(name, [])
            if live:
                raise AlreadyRunning(name, [i["pid"] for i in live])
        proc = subprocess.Popen(argv, env=BASE_ENV,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                start_new_session=True)
        _LAUNCHED.setdefault(name, []).append(
            {"pid": proc.pid, "launched_at": time.time()})
        _save_launched_locked()
    return {"launched": name}


# Launch registry (#491): /api/launch used to spawn one process per request
# with no record of what was already running, so a panel double-tap or a
# retry loop could stack N xterms / N chromiums — each chromium is a heavy
# process. Every spawned PID is recorded here per app name; dead PIDs are
# pruned on every read. ThreadingHTTPServer serves requests on threads,
# so the registry mutates under _LAUNCHED_LOCK; PID reuse is the residual
# false-positive: a recycled PID can briefly report a dead app as running
# until the next prune — acceptable on this localhost, single-operator
# bridge, and it self-heals on the next read.
_LAUNCHED = {}  # app name -> [{"pid": int, "launched_at": float}]
_LAUNCHED_LOCK = threading.Lock()


def _is_alive(pid):
    """Liveness probe for a registry PID (#491).

    Our own children are probed with waitpid(WNOHANG): (0, 0) means still
    running; (pid, _) means it had exited — reaped here, so no zombie
    lingers. The reap matters: launch_app drops the Popen handle without
    wait(), so an exited child is a zombie, and os.kill(pid, 0) succeeds
    on zombies — without the reap, _prune_launched would never drop an
    exited app and singleton would 409 "already running" forever.
    PIDs inherited across a bridge restart are NOT our children (they were
    reparented when the old bridge died), so waitpid raises
    ChildProcessError for those — fall back to the kill(pid, 0) existence
    probe. Unreachable counts as dead, which fails toward allowing a
    duplicate launch (the documented default), never toward a wrongful
    refusal."""
    try:
        rpid, _ = os.waitpid(pid, os.WNOHANG)
        return rpid == 0
    except ChildProcessError:
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True
    except OSError:
        return False


def _prune_launched():
    """Drop dead PIDs from the launch registry. The lock must be held."""
    for app, insts in list(_LAUNCHED.items()):
        live = [inst for inst in insts if _is_alive(inst["pid"])]
        if live:
            _LAUNCHED[app] = live
        else:
            del _LAUNCHED[app]


def launched_instances(app):
    """Live bridge-launched instances for an app name, dead PIDs pruned
    (#491). Returns [{"pid": int, "launched_at": float}]."""
    with _LAUNCHED_LOCK:
        _prune_launched()
        return [dict(i) for i in _LAUNCHED.get(app, [])]


def all_launched():
    """The whole launch registry, pruned — the /api/status "launched"
    payload (#491)."""
    with _LAUNCHED_LOCK:
        _prune_launched()
        return {app: [dict(i) for i in insts]
                for app, insts in _LAUNCHED.items()}


# Registry persistence (#491): the registry above is in-process, but the
# bridge restarts (the keepalive restarts it on failure), and a singleton
# 409 answered from an empty post-restart registry would be a silent
# false negative — the exact retry-after-failure scenario this guards.
# So every mutation persists the registry to ~/.cache (next to the #495
# singleton lock — the flock guarantees this process is the only writer)
# and it is reloaded + pruned at startup. Writes are atomic tmp+rename so
# a crash can never leave a torn file; a failed save warns on stderr but
# never breaks the launch (persistence is best-effort, the guard is not).
# Residual: PID reuse across a reboot can false-positive until the next
# prune — the same best-effort caveat as the in-memory registry.
_LAUNCH_REGISTRY_FILE = os.path.join(_HOME, ".cache", "cua-launched.json")


def _save_launched_locked():
    """Persist the launch registry. The lock must be held."""
    try:
        tmp = _LAUNCH_REGISTRY_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(_LAUNCHED, f)
        os.replace(tmp, _LAUNCH_REGISTRY_FILE)
    except OSError as e:
        print(f"cua-bridge: WARNING: cannot persist launch registry: {e}",
              file=sys.stderr)


def _load_launched():
    """Reload the persisted registry at startup, pruning dead PIDs (#491).
    Corrupt or unreadable files are ignored — never fatal."""
    try:
        with open(_LAUNCH_REGISTRY_FILE) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return
    if not isinstance(data, dict):
        return
    with _LAUNCHED_LOCK:
        _LAUNCHED.clear()
        for app, insts in data.items():
            if not isinstance(app, str) or not isinstance(insts, list):
                continue
            for inst in insts:
                if (isinstance(inst, dict)
                        and isinstance(inst.get("pid"), int)
                        and isinstance(inst.get("launched_at"),
                                       (int, float))):
                    _LAUNCHED.setdefault(app, []).append(
                        {"pid": inst["pid"],
                         "launched_at": float(inst["launched_at"])})
        _prune_launched()


_load_launched()


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


# Concurrency: the stock HTTPServer handles one request at a time, so a slow
# driver call (30s timeout) would head-of-line-block the whole bridge —
# including the keepalive's health probe and a panel's screenshot poll.
# Serve each request on a thread, with a bound on how many handler bodies
# execute at once (cf. #471's unbounded-pool concern on cred-ui/waitlistd).
# Mechanism, stated honestly: ThreadingHTTPServer still spawns one thread
# per accepted connection; the semaphore in process_request_thread bounds
# the number of handlers doing work at any moment, and accepted connections
# beyond the bound block there before touching anything. Threads can pile
# up in the blocked state, so this is not a hard thread cap — acceptable
# on this localhost-only, single-operator bridge, where traffic will never
# approach the bound.
MAX_CONCURRENT_REQUESTS = 8


class BridgeServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._slots = threading.Semaphore(MAX_CONCURRENT_REQUESTS)

    def process_request_thread(self, request, client_address):
        with self._slots:
            super().process_request_thread(request, client_address)


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
        if n > 1_000_000:
            return None  # body too large; caller answers 413
        raw = self.rfile.read(n) if n else b"{}"
        try:
            return json.loads(raw.decode() or "{}")
        except Exception:
            return {}

    def _csrf_ok(self):
        host = (self.headers.get("Host") or "").split(",")[0].strip().lower()
        if host not in ALLOWED_HOSTS:
            return False
        if self.command in ("POST", "PUT", "DELETE"):
            return self.headers.get(CSRF_HEADER) == CSRF_VALUE
        return True

    def _check_csrf(self):
        if not self._csrf_ok():
            self._json({"error": "forbidden"}, 403)
            return False
        return True

    def do_GET(self):
        try:
            if not self._check_csrf():
                return
            if self.path == "/api/status":
                st = subprocess.run([DRIVER, "status"], capture_output=True,
                                    timeout=10, env=BASE_ENV, text=True)
                self._json({"ok": st.returncode == 0,
                            "detail": st.stdout.strip()[:400],
                            # #491 (b): the panel reads the running set here
                            # to decide whether to launch — dead PIDs pruned.
                            "launched": all_launched()})
            elif self.path == "/api/windows":
                self._json(call("list_windows", {}))
            elif self.path == "/api/screenshot":
                # Private 0600 temp file, unlinked right after the read: the
                # old fixed path (/tmp/cua-bridge-shot.png) was a predictable
                # world-readable name in a shared dir — a symlink/snoop
                # surface the moment a second local user exists.
                fd, out = tempfile.mkstemp(suffix=".png", prefix="cua-shot-")
                os.close(fd)
                try:
                    call("get_desktop_state", {"screenshot_out_file": out})
                    with open(out, "rb") as f:
                        png = f.read()
                finally:
                    try:
                        os.unlink(out)
                    except OSError:
                        pass
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
            if not self._check_csrf():
                return
            data = self._body()
            if data is None:
                return self._json({"error": "body too large"}, 413)
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
                # #491 (a-as-opt-in): the caller asked for at most one
                # instance. Only a literal JSON true opts in — a "false"
                # string must not silently become a singleton refusal.
                # The default stays multi-launch: a second xterm is
                # sometimes wanted.
                singleton = data.get("singleton") is True
                try:
                    res = launch_app(app, singleton=singleton)
                except AlreadyRunning as e:
                    return self._json({"error": "already running",
                                       "pids": e.pids}, 409)
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
    # Singleton guard (#495): overlapping keepalive invocations (or a manual
    # double-start) must not run two bridges — the second bind would fail
    # silently under the keepalive's setsid. Exit rather than limp.
    if acquire_singleton_lock() is None:
        print("cua-bridge: another instance is already running; exiting",
              file=sys.stderr)
        sys.exit(1)
    srv = BridgeServer(("127.0.0.1", PORT), Handler)
    print(f"cua-bridge listening on 127.0.0.1:{PORT}", flush=True)
    srv.serve_forever()
