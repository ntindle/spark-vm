#!/usr/bin/env python3
"""cua-bridge — localhost HTTP bridge to the CUA Driver desktop on spark-vm.

Listens on 127.0.0.1 only. The private control-panel artifact's backend
calls this over an SSH tunnel from the hatch VM; it shells out to
`cua-driver call` against the spark-vm desktop display (:98). No arbitrary
shell: only the allowlisted desktop actions.

Endpoints:
  GET  /api/status      -> stack + driver state
  GET  /api/liveness    -> bridge-alive probe (no driver call; the restart
                           signal for keepalives — a slow driver can never
                           false-trip it)
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
import ctypes
import ctypes.util
import errno
import fcntl
import json
import os
import select
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

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


def _valid_registry_pid(pid):
    """A registry PID must be a genuine positive pid.

    Bools are ints in Python (True == 1), pid 0 is special to
    waitpid()/kill(): _is_alive(0) always reports alive (the process
    group itself is non-empty), and pid 1 (init) is equally unprunable —
    kill(1, 0) succeeds, so _is_alive(1) always reports alive. A
    persisted {"pid": 0}, {"pid": True} (== 1), or {"pid": 1} would never
    prune and the singleton guard would 409 "already running" forever.
    Reject them here: corrupt/malicious entries are dropped, never fatal.
    """
    return type(pid) is int and pid > 1


def _open_tmp_exclusive(path):
    """Create path exclusively (O_EXCL|O_NOFOLLOW, 0600); return fd or None.

    A pre-existing path — a stale tmp from a crash, or a planted
    symlink (O_NOFOLLOW refuses to follow it) — is unlinked once and
    the file re-created exclusively. Anything else failing (unwritable
    dir, double race) returns None; the caller warns and continues.
    """
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    try:
        return os.open(path, flags, 0o600)
    except OSError as e:
        if e.errno not in (errno.EEXIST, errno.ELOOP):
            return None
    try:
        os.unlink(path)
    except OSError:
        return None
    try:
        return os.open(path, flags, 0o600)
    except OSError:
        return None


def _save_launched_locked():
    """Persist the launch registry. The lock must be held.

    The tmp file is created with O_EXCL|O_NOFOLLOW at 0600, so the
    write can never follow a planted symlink or clobber an existing
    file. Atomic tmp+rename keeps the registry itself tear-free; a
    failed save warns on stderr but never breaks the launch
    (persistence is best-effort, the guard is not).
    """
    tmp = _LAUNCH_REGISTRY_FILE + ".tmp"
    payload = json.dumps(_LAUNCHED).encode()
    fd = _open_tmp_exclusive(tmp)
    if fd is None:
        print("cua-bridge: WARNING: cannot persist launch registry: "
              "exclusive tmp create failed", file=sys.stderr)
        return
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(payload)
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
                        and _valid_registry_pid(inst.get("pid"))
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
    # "foreground" for type/key instead of the focus + targeted calls the
    # /api/type and /api/key handlers make: untargeted, the foreground key
    # routes through XTEST global input, which delivers to whatever window
    # happens to hold input focus — XTEST ignores the target and goes to
    # focus, verified with xev. XSendEvent works, but only to a focused
    # window.)
    # The input probe (#492) relies on the other half of this contract:
    # with xev focused, the untargeted XTEST key lands in xev and echoes.
    # ASSUMPTION, pinned to cua-driver 0.28.2 (cua/README.md): untargeted
    # foreground press_key routes through XTestFakeKeyEvent. Re-verify this
    # routing if the driver is upgraded — if untargeted keys ever route via
    # XSendEvent instead, the probe will false-report "ok" on a wedged
    # keyboard, because XSendEvent survives the wedge.
    call("bring_to_front", {"pid": w["pid"], "window_id": w["window_id"]})


_XA_WINDOW = 33  # predefined X atom id for the WINDOW property type

_x11 = None          # cached libX11 CDLL once loaded
_x11_failed = False  # latched once a load attempt has failed
_x11_lock = threading.Lock()  # serializes the lazy load: the bridge is
# threaded, and without it a racing failed load could latch _x11_failed
# while a sibling load would have succeeded, permanently disabling the
# assertion for the process


def _x11_lib():
    """Load libX11 once via stdlib ctypes (no new dependency). Returns the
    CDLL, or None when libX11 cannot be loaded on this machine. Never
    raises — a missing X client library only means the focus assertion
    cannot run (fail-open, loudly, in _assert_focused)."""
    global _x11, _x11_failed
    if _x11_failed:
        return None
    if _x11 is not None:
        return _x11
    with _x11_lock:
        if _x11_failed:
            return None
        if _x11 is not None:
            return _x11
        try:
            name = ctypes.util.find_library("X11") or "libX11.so.6"
            lib = ctypes.CDLL(name)
            lib.XOpenDisplay.argtypes = [ctypes.c_char_p]
            lib.XOpenDisplay.restype = ctypes.c_void_p
            lib.XCloseDisplay.argtypes = [ctypes.c_void_p]
            lib.XCloseDisplay.restype = ctypes.c_int
            lib.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
            lib.XDefaultRootWindow.restype = ctypes.c_ulong
            lib.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p,
                                        ctypes.c_int]
            lib.XInternAtom.restype = ctypes.c_ulong
            lib.XFree.argtypes = [ctypes.c_void_p]
            lib.XFree.restype = ctypes.c_int
            lib.XGetWindowProperty.argtypes = [
                ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong,
                ctypes.c_long, ctypes.c_long, ctypes.c_int, ctypes.c_ulong,
                ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_int),
                ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_ulong),
                ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte))]
            lib.XGetWindowProperty.restype = ctypes.c_int
            _x11 = lib
        except Exception:
            _x11_failed = True
            return None
    return _x11


def _active_window_id():
    """Best-effort read of the EWMH _NET_ACTIVE_WINDOW root property — the
    same property bring_to_front sets through the driver.

    Returns the active X11 window id (int), or None when it cannot be
    determined: no libX11, no display name, the WM doesn't publish the
    property (non-EWMH WMs), or any X error short of a fatal Xlib protocol
    error (unreachable with the validated display/root/atom used here).
    Never raises; no per-call subprocesses (one `ldconfig` probe may run
    at first load inside `ctypes.util.find_library`). The display name
    comes from BASE_ENV (the bridged desktop's env) — when BASE_ENV has
    no DISPLAY the target desktop is unknown and the read fails open —
    so the read always targets the desktop the bridge drives, never a
    stray ambient display.
    """
    lib = None
    prop = ctypes.POINTER(ctypes.c_ubyte)()
    d = None
    try:
        lib = _x11_lib()
        if lib is None:
            return None
        display = BASE_ENV.get("DISPLAY")
        if not display:
            return None
        d = lib.XOpenDisplay(display.encode())
        if not d:
            return None
        atom = lib.XInternAtom(d, b"_NET_ACTIVE_WINDOW", False)
        root = lib.XDefaultRootWindow(d)
        actual_type = ctypes.c_ulong()
        actual_format = ctypes.c_int()
        nitems = ctypes.c_ulong()
        bytes_after = ctypes.c_ulong()
        rc = lib.XGetWindowProperty(
            d, root, atom, 0, 1, False, _XA_WINDOW,
            ctypes.byref(actual_type), ctypes.byref(actual_format),
            ctypes.byref(nitems), ctypes.byref(bytes_after),
            ctypes.byref(prop))
        if rc != 0 or nitems.value < 1 or not prop:
            return None
        return int(ctypes.cast(prop, ctypes.POINTER(ctypes.c_ulong))[0])
    except Exception:
        return None
    finally:
        try:
            if prop:
                lib.XFree(prop)
        except Exception:
            pass
        try:
            if d:
                lib.XCloseDisplay(d)
        except Exception:
            pass


_FOCUS_SETTLE_S = 0.5    # per-attempt budget waiting for the WM to publish
# _NET_ACTIVE_WINDOW after bring_to_front (polled, not slept — a fast WM
# grants focus on the first poll)
_FOCUS_POLL_STEP_S = 0.05


def _poll_focus(target_id, deadline):
    """Poll _NET_ACTIVE_WINDOW until target_id appears or the deadline
    passes. Returns (matched, readable): readable tells whether any poll
    returned a value at all, so callers can distinguish "stolen focus"
    from "the WM doesn't publish focus".

    Two consecutive unreadable reads short-circuit the poll: a missing
    libX11, an unreachable display, or a non-EWMH WM is deterministic —
    the property will not become readable later in this poll — so there
    is no reason to burn the whole settle budget (which would otherwise
    eat the #492 probe's echo-observation budget on exotic stacks). A
    merely slow WM still returns a *wrong* id, not None, so the
    grant-latency case keeps its full settle."""
    readable = False
    none_streak = 0
    while True:
        active = _active_window_id()
        if active is None:
            none_streak += 1
            if none_streak >= 2:
                # Keep any earlier readability: a transient X hiccup after
                # a readable (wrong) id must not downgrade a stolen-focus
                # signal into fail-open.
                return False, readable
        else:
            readable = True
            none_streak = 0
            if active == target_id:
                return True, True
        if time.monotonic() >= deadline:
            return False, readable
        time.sleep(_FOCUS_POLL_STEP_S)


def _assert_focused(w):
    """Confirm w still holds input focus before keystrokes are delivered
    (#494).

    bring_to_front is asynchronous — the WM grants _NET_ACTIVE_WINDOW on
    its own schedule — and another client can steal focus at any moment,
    in which case the driver's XTEST injection would land in the wrong
    window (XTEST delivers to the focus window and ignores the target).
    Poll the EWMH active-window property — the same property
    bring_to_front sets — for the target id; on a persistent mismatch,
    re-assert focus once and re-poll, then give up LOUDLY (False) instead
    of typing into the wrong window.

    When the property cannot be read at all (no libX11, no display, a
    non-EWMH WM), fail OPEN — fast, after two consecutive unreadable reads,
    with a loud log: typing availability on exotic stacks outranks an
    unverifiable assertion, and the fast path keeps the #492 probe's echo
    budget intact; the stolen-focus case — the shape #494 names — stays
    fail-closed.

    Residual, stated honestly: this narrows the bridge-side window to the
    final-poll→driver-call race (stolen focus between bring_to_front and
    the driver call). The driver's own
    foreground sequence re-activates the target inside the call, but a
    focus steal landing between the driver's activate and its inject is
    driver-internal and cannot be closed from the bridge — closing that
    needs an atomic focus+inject driver operation (upstream).
    """
    target_id = int(w["window_id"])
    matched, readable = _poll_focus(target_id,
                                    time.monotonic() + _FOCUS_SETTLE_S)
    if matched:
        return True
    if not readable:
        # Never saw a readable property — the WM doesn't publish it or X
        # is unreachable; fail open, loudly (see docstring).
        print("cua-bridge: WARNING: _NET_ACTIVE_WINDOW unreadable — focus "
              "assertion skipped (fail-open); exotic/non-EWMH stack?",
              file=sys.stderr)
        return True
    # Readable but wrong: one re-assert + re-poll (a slow WM, or a
    # transient raise interleaved with the first bring_to_front), then
    # fail closed.
    try:
        focus_window(w)
    except Exception as e:
        print(f"cua-bridge: focus re-assert failed: {e}", file=sys.stderr)
        return False
    matched, _ = _poll_focus(target_id, time.monotonic() + _FOCUS_SETTLE_S)
    if matched:
        return True
    print(f"cua-bridge: FOCUS ASSERTION FAILED for window {target_id} "
          f"(pid {w.get('pid')}) — keystrokes NOT delivered (#494)",
          file=sys.stderr)
    return False


# Input-path liveness probe (#492): /api/status used to report
# driver-process health only, so the stack's best-known failure mode — the
# Xvfb XTEST keyboard device wedging while the driver keeps reporting
# success — was invisible: a healthy-but-unusable desktop. The bridge now
# exposes the probe in two halves:
#
# - Plain GET /api/status is a read-only health check. It serves the last
#   probe outcome from the cache below — it never spawns xev, never steals
#   focus, never injects a key. The keepalive's 5-minute poll (which
#   discards the body) is unaffected.
# - GET /api/status?probe=1 runs a fresh probe, single-flight: concurrent
#   callers share the in-flight probe instead of each spawning xev (two
#   overlapping probes would cross-talk — one's XTEST key landing in the
#   other's xev — and false-report a wedge).
#
# The probe automates the documented manual diagnosis: spawn `xev` on :98,
# focus its window, send one harmless XTEST key (a bare Shift tap, which
# does nothing visible anywhere) through the driver's untargeted
# global-input route, and wait for xev's KeyPress echo.
INPUT_PROBE_TIMEOUT = 2.0  # seconds; keeps a probing /api/status well under
# the keepalive's curl --max-time 5 liveness check
_INPUT_PROBE_KEY = "Shift_L"
_ECHO_FLOOR_S = 0.5  # minimum echo-wait budget after the key is sent; less
# than this is not a real observation — a late-appearing xev window must
# report "unknown", never a zero-observation "wedged"
# ASSUMPTION (B4), pinned to cua-driver 0.28.2 (cua/README.md): untargeted
# foreground press_key routes through XTestFakeKeyEvent — see the
# focus_window contract note. Re-verify on driver upgrades.
# #494: bring_to_front is async and focus can be stolen between it and
# the keystroke injection, so the /api/type and /api/key handlers (and
# the #492 probe) re-verify the target through _assert_focused() before
# delivering input — a persistent mismatch fails closed (409 /
# "unknown") instead of typing into the wrong window. ASSUMPTION, pinned
# to cua-driver 0.28.2 like (B4) above: the read trusts that
# bring_to_front keeps publishing _NET_ACTIVE_WINDOW — re-verify on
# driver upgrades.
PROBE_DRIVER_VERSION = "cua-driver 0.28.2"

# Serializes probe bodies: XTestFakeKeyEvent delivers to the focus window,
# not to any xev in particular, so two overlapping probes cross-talk.
_INPUT_PROBE_LOCK = threading.Lock()


def _input_probe(timeout=INPUT_PROBE_TIMEOUT, cancel=None):
    """One attempt at the XTEST keyboard-path liveness check (#492).

    `cancel` is a threading.Event the budget wrapper sets when the probe
    overruns: side-effecting steps (focus hop, key injection) are skipped
    once cancelled, so an orphaned probe thread never mutates the desktop
    after its request already returned.

    Returns (state, detail):
      "ok"      — KeyPress echo seen; the XTEST input path is live.
      "wedged"  — xev ran, got focus, the XTEST key was sent, and a full
                  echo observation window passed with no KeyPress: the
                  XTEST keyboard device is wedged. Remediation:
                  `cua-desktop.sh stop` + `start` (fresh Xvfb; only touches
                  :98).
      "unknown" — the probe itself could not run or could not observe
                  (xev/stdbuf missing, the xev window never appeared, the
                  driver rejected the untargeted key, xev exited before
                  echoing, the window appeared too late for a real echo
                  wait, the budget blew). A probe failure is never reported
                  as a wedge — that is the fail-safe direction.

    The focus hop is inherent to the check: XTestFakeKeyEvent delivers to
    the input-focus window, so xev must hold focus for the echo to land in
    it. The pre-probe focused window is restored afterwards (best-effort).
    xev's stdout is line-buffered through stdbuf — without it, the piped
    KeyPress line would sit in a 4 KiB block buffer and the probe would
    false-report a wedge. The probe never shells out: fixed argv only, both
    binaries resolved to absolute paths against the bridge's own PATH so
    the check and the exec cannot diverge.
    """
    with _INPUT_PROBE_LOCK:
        if cancel is not None and cancel.is_set():
            return ("unknown",
                    "input probe cancelled before start — inconclusive")
        path = BASE_ENV.get("PATH", "")
        xev = shutil.which("xev", path=path)
        if xev is None:
            return ("unknown",
                    "xev is not installed — cannot run the input-path probe")
        stdbuf = shutil.which("stdbuf", path=path)
        if stdbuf is None:
            return ("unknown",
                    "stdbuf is not installed — xev output would be "
                    "block-buffered and the probe could false-report a wedge")
        # Best-effort focus restore: remember what had focus before the
        # probe's own focus hop, so the net effect is ~neutral.
        prev = None
        try:
            prev = top_window()
        except Exception:
            prev = None
        deadline = time.monotonic() + timeout
        try:
            proc = subprocess.Popen(
                [stdbuf, "-oL", "-eL", xev, "-event", "keyboard"],
                env=BASE_ENV, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, start_new_session=True)
        except OSError as e:
            return ("unknown", f"cannot spawn xev: {e}"[:200])
        focused = False
        try:
            win = None
            while time.monotonic() < deadline:
                if cancel is not None and cancel.is_set():
                    return ("unknown",
                            "input probe cancelled — inconclusive")
                wins = call("list_windows", {}).get("windows", [])
                # Match on the exact child PID: window titles and app names
                # are free-form and settable by any X client, so a spoofed
                # "Event Tester" window could otherwise steal the focus and
                # the key and false-report a wedge. No PID match is
                # inconclusive, never a wedge.
                hits = [w for w in wins
                        if w.get("is_on_screen") and w.get("pid") == proc.pid]
                if hits:
                    win = max(hits, key=lambda w: w.get("z_index", 0))
                    break
                time.sleep(0.1)
            if win is None:
                return ("unknown",
                        f"xev (pid {proc.pid}) never appeared in "
                        "list_windows — probe inconclusive")
            if cancel is not None and cancel.is_set():
                return ("unknown",
                        "input probe cancelled before the focus hop — "
                        "inconclusive")
            focus_window(win)
            focused = True
            if cancel is not None:
                if cancel.wait(0.2):  # let the WM grant focus; abort early
                    return ("unknown",
                            "input probe cancelled — inconclusive")
            else:
                time.sleep(0.2)
            if cancel is not None and cancel.is_set():
                return ("unknown",
                        "input probe cancelled before the key — inconclusive")
            # #494: the untargeted key below lands wherever input focus is.
            # If focus was stolen after the hop, the echo would never arrive
            # and the probe would false-report a wedge — verify first, and
            # report the theft as inconclusive (the fail-safe direction).
            if not _assert_focused(win):
                return ("unknown",
                        "focus stolen between the probe's focus hop and the "
                        "XTEST key — a missing echo would false-report a "
                        "wedge; probe inconclusive")
            # No pid/window_id: the untargeted foreground key routes through
            # XTEST global input and lands in the focused window (xev). A
            # bare modifier tap is harmless wherever it lands.
            try:
                call("press_key", {"key": _INPUT_PROBE_KEY, "modifiers": [],
                                   "delivery_mode": "foreground"})
            except Exception as e:
                return ("unknown",
                        f"driver rejected the global input key: {e}"[:200])
            if deadline - time.monotonic() < _ECHO_FLOOR_S:
                return ("unknown",
                        "xev appeared too late in the probe budget for a "
                        "meaningful echo wait — inconclusive")
            fd = proc.stdout.fileno()
            os.set_blocking(fd, False)
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                r, _, _ = select.select([fd], [], [], remaining)
                if not r:
                    break
                try:
                    chunk = os.read(fd, 65536)
                except BlockingIOError:
                    continue
                if not chunk:
                    # xev exited before echoing: a probe failure, not wedge
                    # evidence — the fail-safe direction.
                    return ("unknown",
                            "xev exited before echoing a KeyPress — probe "
                            "inconclusive")
                if b"KeyPress" in chunk:
                    elapsed = timeout - max(remaining, 0)
                    return ("ok",
                            "XTEST KeyPress echo observed in "
                            f"{elapsed:.1f}s")
            return ("wedged",
                    "no KeyPress echo from the XTEST key within "
                    f"{timeout:.0f}s — the XTEST keyboard device is wedged; "
                    "restart the desktop stack (cua-desktop.sh stop/start)")
        except Exception as e:
            return ("unknown", f"input probe error: {e}"[:200])
        finally:
            try:
                proc.stdout.close()
            except Exception:
                pass
            try:
                proc.kill()
                proc.wait(timeout=5)
            except Exception:
                pass
            if focused and prev is not None:
                try:
                    focus_window(prev)
                except Exception:
                    pass


def _bounded_probe(timeout=INPUT_PROBE_TIMEOUT):
    """Run _input_probe on a daemon thread with a hard budget (#492).

    The probe makes several driver calls, each with the driver's own long
    timeout — a hung driver must not stall /api/status past the keepalive's
    curl --max-time 5 liveness check, or the keepalive would restart a
    healthy bridge. A blown budget is reported as "unknown" (inconclusive),
    never as a wedge, and the cancel event keeps the orphaned thread from
    performing focus/key side effects after its request already returned.
    """
    cancel = threading.Event()
    result = {}

    def run():
        try:
            result["outcome"] = _input_probe(timeout, cancel)
        except Exception as e:  # never let the probe crash the status handler
            result["outcome"] = ("unknown", f"input probe crashed: {e}"[:200])

    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        cancel.set()
        return ("unknown",
                "input probe exceeded its "
                f"{timeout:.0f}s budget — inconclusive")
    return result.get("outcome",
                      ("unknown", "input probe produced no result"))


# Last probe outcome, served by plain GET /api/status (read-only).
_probe_lock = threading.Lock()
_probe_cache = {"state": "unknown",
                "detail": "input probe has not run yet — "
                          "request /api/status?probe=1",
                "checked_at": None}
_probe_inflight = False


def get_input_liveness(run_probe=False):
    """The /api/status "input" field (#492).

    Plain calls serve the cached outcome — a pure read. run_probe=True
    (GET /api/status?probe=1) runs a fresh probe, single-flight: while one
    probe is in flight, concurrent callers get the last cached outcome
    instead of spawning their own xev. Returns (state, detail, checked_at);
    checked_at is epoch seconds, or None when the probe has never run.
    """
    global _probe_inflight
    with _probe_lock:
        if not run_probe or _probe_inflight:
            c = _probe_cache
            return (c["state"], c["detail"], c["checked_at"])
        _probe_inflight = True
    try:
        state, detail = _bounded_probe()
    finally:
        with _probe_lock:
            _probe_cache.update(state=state, detail=detail,
                                checked_at=time.time())
            _probe_inflight = False
    with _probe_lock:
        c = _probe_cache
        return (c["state"], c["detail"], c["checked_at"])


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
        # Issue #1228: nosniff — the bridge is API-only (JSON + one PNG),
        # so content-type confusion is the only sniffing risk; nothing
        # here is framed, so X-Frame-Options is not needed.
        self.send_header("X-Content-Type-Options", "nosniff")
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

    def _focus_409(self):
        # #494: the focus assertion failed — refuse loudly instead of
        # delivering keystrokes to whatever stole focus.
        return self._json(
            {"error": "focus assertion failed — another window holds "
                      "input focus; keystrokes not delivered (#494)"}, 409)

    def do_GET(self):
        try:
            if not self._check_csrf():
                return
            parsed = urlparse(self.path)
            if parsed.path == "/api/liveness":
                # #784: liveness is decoupled from driver health. The
                # keepalive's restart decision must answer "is the BRIDGE
                # alive?" — not "is the DRIVER fast?". /api/status shells
                # out to `cua-driver status` with a 10s budget, so a slow
                # driver used to false-trip the keepalive's 5s curl budget
                # into a spurious bridge restart; restarting the bridge
                # can't fix a slow driver anyway. This endpoint never
                # spawns a subprocess, never touches the probe cache —
                # it answers in microseconds, so the keepalive's budget
                # can only expire when the bridge is genuinely down.
                # /api/status keeps the full driver detail for panels
                # and operators.
                self._json({"alive": True})
            elif parsed.path == "/api/status":
                st = subprocess.run([DRIVER, "status"], capture_output=True,
                                    timeout=10, env=BASE_ENV, text=True)
                if st.returncode == 0:
                    # ?probe=1 runs a fresh input probe (single-flight);
                    # plain /api/status is a pure read serving the last
                    # cached probe outcome — never spawns xev.
                    probe_requested = (parse_qs(parsed.query).get("probe")
                                       == ["1"])
                    pstate, pdetail, pchecked = get_input_liveness(
                        run_probe=probe_requested)
                else:
                    # driver down: the input path cannot be probed either
                    pstate, pdetail, pchecked = (
                        "unknown", "driver down — input probe skipped", None)
                self._json({"ok": st.returncode == 0,
                            "detail": st.stdout.strip()[:400],
                            # #491 (b): the panel reads the running set here
                            # to decide whether to launch — dead PIDs pruned.
                            "launched": all_launched(),
                            # #492: driver-process health alone cannot see
                            # the XTEST keyboard wedge (input silently dead
                            # while the driver reports ok) — "input" reports
                            # the XTEST-path liveness probe:
                            # "ok" | "wedged" | "unknown". "driver" pins the
                            # driver version the probe's XTEST-routing
                            # assumption was verified against.
                            "input": {"state": pstate,
                                      "detail": pdetail,
                                      "checked_at": pchecked,
                                      "driver": PROBE_DRIVER_VERSION}})
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
                # Issue #1228: nosniff — same rationale as _json above.
                self.send_header("X-Content-Type-Options", "nosniff")
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
                if not _assert_focused(w):
                    return self._focus_409()
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
                if not _assert_focused(w):
                    return self._focus_409()
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
