#!/bin/bash
# cua-desktop.sh — supervise the CUA desktop stack on spark-vm (display :98).
# Components: Xvfb, D-Bus session, XFCE desktop, cua-driver daemon.
# Idempotent: safe to re-run. Run: cua-desktop.sh start|stop|status
#
# NOTE: spark-vm's GNOME session runs on Wayland (not drivable by the X11
# driver) and BlenderMCP owns Xvfb :99 — this stack uses a separate :98.
set -u
export PATH="$HOME/cua/bin:/usr/local/bin:/usr/bin:/bin"

# Shared env-file trust predicate (#493) — the same check every consumer
# of the desktop env file applies.
# shellcheck disable=SC1091
. "$(dirname "${BASH_SOURCE[0]}")/cua-trust.sh"

RUNDIR=/tmp/cua-desktop
DISPLAY_NUM=98
SOCK="$HOME/.cache/cua-driver/cua-driver.sock"
DRIVER_BIN="$HOME/cua/bin/cua-driver"

# Secure the rundir (#493): it holds the desktop env file that the bridge,
# the driver launchers, and the keepalive all consume, and /tmp is
# world-writable. Create it with 0700 (atomically via -m, so there is no
# umask window for a watching local user); if it already exists, verify it
# is a real directory owned by us and repair the mode — a symlink or a dir
# owned by someone else is a plant and fails loudly (plain `mkdir -p`
# would silently accept either). Also the single choke point for stale
# env-file plants: an existing $RUNDIR/env that fails the trust check is
# removed here (do_start regenerates it below), so no consumer can source
# pre-fix planted contents.
ensure_private_rundir() {
  if [ -L "$RUNDIR" ]; then
    echo "cua-desktop: $RUNDIR is a symlink (possible plant), refusing to proceed" >&2
    return 1
  fi
  if mkdir -m 700 "$RUNDIR" 2>/dev/null; then
    :
  else
    # mkdir lost the race or the dir pre-existed: re-check for a symlink
    # before any dereferencing operation (a swap between the check above
    # and mkdir would otherwise get chmod applied through the link).
    if [ -L "$RUNDIR" ]; then
      echo "cua-desktop: $RUNDIR is a symlink (possible plant), refusing to proceed" >&2
      return 1
    fi
    [ -d "$RUNDIR" ] || {
      echo "cua-desktop: $RUNDIR exists but is not a directory, refusing to proceed" >&2
      return 1
    }
    if [ "$(stat -c %U "$RUNDIR")" != "$(id -un)" ]; then
      echo "cua-desktop: $RUNDIR is owned by another user (possible plant), refusing to proceed" >&2
      return 1
    fi
    chmod 700 "$RUNDIR" || return 1
  fi
  if [ -e "$RUNDIR/env" ] && ! trust_env_file "$RUNDIR/env"; then
    echo "cua-desktop: WARNING: $RUNDIR/env failed the trust check (possible plant) — removing it" >&2
    rm -f "$RUNDIR/env" || return 1
  fi
}
ensure_private_rundir || exit 1

running() { # running <pidfile>
  [ -f "$1" ] && kill -0 "$(cat "$1")" 2>/dev/null
}

# Input-path liveness surfacing (#769): read the bridge's probe-cache
# verdict and render it in the status vocabulary, so an operator sees the
# XTEST wedge without reading the bridge log. Best-effort: an unreachable
# bridge or a missing curl/python3 prints nothing and must never break
# the status command.
# shellcheck disable=SC2120 # tests (cua/test_shell_scripts.py) call
# surface_input_probe with a bridge_url override; the production call site
# passes none.
surface_input_probe() { # surface_input_probe [bridge_url] — arg override exists for tests
  local bridge=${1:-http://127.0.0.1:18731}
  if command -v curl >/dev/null 2>&1 && command -v python3 >/dev/null 2>&1; then
    local probe_body probe_state
    probe_body=$(curl -s --max-time 5 "$bridge/api/status" 2>/dev/null) || probe_body=""
    if [ -n "$probe_body" ]; then
      probe_state=$(printf '%s' "$probe_body" | python3 -c \
        'import json,sys
try:
    print(json.load(sys.stdin).get("input", {}).get("state", "unknown"))
except Exception:
    print("unparseable")' 2>/dev/null) || probe_state=""
      case "$probe_state" in
        ok) echo "[ok] input path (XTEST probe)" ;;
        wedged) echo "[wedged] input path (XTEST probe) — remediate: cua-desktop.sh stop && cua-desktop.sh start" ;;
        unknown) echo "[unknown] input path (probe not run yet or inconclusive)" ;;
      esac
    fi
  fi
}

do_start() {
  # 1. Xvfb
  if ! running "$RUNDIR/xvfb.pid"; then
    rm -f /tmp/.X${DISPLAY_NUM}-lock
    setsid Xvfb :$DISPLAY_NUM -screen 0 1280x800x24 >"$RUNDIR/xvfb.log" 2>&1 < /dev/null &
    echo $! > "$RUNDIR/xvfb.pid"
    # Verify Xvfb actually bound the display; otherwise everything below
    # would start against a dead display.
    for _i in 1 2 3 4 5; do
      [ -S /tmp/.X11-unix/X$DISPLAY_NUM ] && break
      sleep 1
    done
    if [ ! -S /tmp/.X11-unix/X$DISPLAY_NUM ]; then
      echo "cua-desktop: Xvfb failed to bind :$DISPLAY_NUM (see $RUNDIR/xvfb.log)" >&2
      return 1
    fi
  fi
  # 2. D-Bus session
  if ! running "$RUNDIR/dbus.pid"; then
    dbus-daemon --session --fork --print-address=1 --print-pid=1 > "$RUNDIR/dbus.env" 2>/dev/null
    DBUS_ADDR=$(head -1 "$RUNDIR/dbus.env"); DBUS_PID=$(tail -1 "$RUNDIR/dbus.env")
    echo "$DBUS_PID" > "$RUNDIR/dbus.pid"
    printf 'export DISPLAY=:%s\nexport DBUS_SESSION_BUS_ADDRESS=%s\n' "$DISPLAY_NUM" "$DBUS_ADDR" > "$RUNDIR/env"
    chmod 600 "$RUNDIR/env"
  elif [ ! -f "$RUNDIR/env" ]; then
    # ensure_private_rundir removed an untrusted env file (or it was lost):
    # regenerate from the recorded dbus address rather than running sourceless.
    DBUS_ADDR=$(head -1 "$RUNDIR/dbus.env" 2>/dev/null)
    printf 'export DISPLAY=:%s\nexport DBUS_SESSION_BUS_ADDRESS=%s\n' "$DISPLAY_NUM" "$DBUS_ADDR" > "$RUNDIR/env"
    chmod 600 "$RUNDIR/env"
  fi
  # NOTE: the env file is safe to source here — ensure_private_rundir above
  # removed anything failing the trust check, and the writes just above are
  # ours with mode 0600 (writer and trust gate agree regardless of umask).
  # shellcheck disable=SC1091
  source "$RUNDIR/env"
  # 3. Desktop environment: XFCE as individual components
  # (xfwm4 + xfce4-panel taskbar + xfdesktop), via start-xfce.sh.
  # NOTE: xfce4-session does NOT work headless here (its children inherit a
  # Wayland-probing environment and crash), and every GTK app needs
  # GDK_BACKEND=x11 (see start-xfce.sh) or xfce4-panel segfaults in libwnck.
  # Openbox remains as a manual fallback only.
  "$HOME/cua/bin/start-xfce.sh" >/dev/null 2>&1
  # 4. cua-driver daemon
  if ! "$DRIVER_BIN" status >/dev/null 2>&1; then
    setsid "$DRIVER_BIN" serve --socket "$SOCK" >"$RUNDIR/driver.log" 2>&1 < /dev/null &
    echo $! > "$RUNDIR/driver.pid"
    sleep 3
  fi
  do_status
}

do_stop() {
  # bracket-trick patterns so pkill never matches this script's own cmdline
  pkill -f "cua-driver serv[e]" 2>/dev/null
  pkill -f "xfce4-sessio[n]" 2>/dev/null
  pkill -f "xfce4-pane[l]" 2>/dev/null
  pkill -f "xfdeskt[o]p" 2>/dev/null
  pkill -f "openbo[x]" 2>/dev/null
  pkill -f "[x]fwm4" 2>/dev/null
  for p in driver.pid wm.pid dbus.pid xvfb.pid xfwm4.pid panel.pid xfdesktop.pid; do
    if running "$RUNDIR/$p"; then kill "$(cat "$RUNDIR/$p")" 2>/dev/null; fi
    rm -f "$RUNDIR/$p"
  done
  rm -f /tmp/.X${DISPLAY_NUM}-lock
  echo "stopped"
}

do_status() {
  # NOTE: safe to source — ensure_private_rundir (top of this script) removed
  # any env file failing the trust check before we get here, and the 0700
  # rundir keeps other users from replacing it between the check and this.
  # shellcheck disable=SC1091
  [ -f "$RUNDIR/env" ] && source "$RUNDIR/env"
  for c in "xvfb:Xvfb" "dbus:D-Bus" "driver:cua-driver daemon"; do
    p="${c%%:*}"; label="${c#*:}"
    if running "$RUNDIR/$p.pid"; then echo "[ok] $label (pid $(cat "$RUNDIR/$p.pid"))";
    else echo "[down] $label"; fi
  done
  # desktop is healthy only when all three XFCE components are up
  if running "$RUNDIR/xfwm4.pid" && running "$RUNDIR/panel.pid" && running "$RUNDIR/xfdesktop.pid"; then
    echo "[ok] desktop (XFCE: xfwm4+panel+xfdesktop)"
  else
    echo "[down] desktop (XFCE)"
  fi
  if [ -x "$DRIVER_BIN" ]; then
    DISPLAY=:$DISPLAY_NUM "$DRIVER_BIN" status 2>&1 | head -4
  fi
  # Input-path liveness (#769): the bridge's probe cache is refreshed on
  # the keepalive's schedule — surface the last verdict here so an
  # operator sees the XTEST wedge without reading the bridge log.
  surface_input_probe
}

case "${1:-status}" in
  start) do_start ;;
  stop) do_stop ;;
  status) do_status ;;
  *) echo "usage: $0 start|stop|status" >&2; exit 2 ;;
esac
