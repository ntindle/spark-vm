#!/bin/bash
# cua-desktop.sh — supervise the CUA desktop stack on spark-vm (display :98).
# Components: Xvfb, D-Bus session, XFCE desktop, cua-driver daemon.
# Idempotent: safe to re-run. Run: cua-desktop.sh start|stop|status
#
# NOTE: spark-vm's GNOME session runs on Wayland (not drivable by the X11
# driver) and BlenderMCP owns Xvfb :99 — this stack uses a separate :98.
set -u
export PATH="/home/ntindle/cua/bin:/usr/local/bin:/usr/bin:/bin"

RUNDIR=/tmp/cua-desktop
DISPLAY_NUM=98
SOCK="/home/ntindle/.cache/cua-driver/cua-driver.sock"
DRIVER_BIN="/home/ntindle/cua/bin/cua-driver"

mkdir -p "$RUNDIR"

running() { # running <pidfile>
  [ -f "$1" ] && kill -0 "$(cat "$1")" 2>/dev/null
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
  fi
  # shellcheck disable=SC1091
  source "$RUNDIR/env"
  # 3. Desktop environment: XFCE as individual components
  # (xfwm4 + xfce4-panel taskbar + xfdesktop), via start-xfce.sh.
  # NOTE: xfce4-session does NOT work headless here (its children inherit a
  # Wayland-probing environment and crash), and every GTK app needs
  # GDK_BACKEND=x11 (see start-xfce.sh) or xfce4-panel segfaults in libwnck.
  # Openbox remains as a manual fallback only.
  "/home/ntindle/cua/bin/start-xfce.sh" >/dev/null 2>&1
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
}

case "${1:-status}" in
  start) do_start ;;
  stop) do_stop ;;
  status) do_status ;;
  *) echo "usage: $0 start|stop|status" >&2; exit 2 ;;
esac
