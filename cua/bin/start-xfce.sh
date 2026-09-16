#!/bin/bash
# start-xfce.sh — launch XFCE desktop components on :98 with a sanitized env.
# GDK_BACKEND=x11 is REQUIRED: without it, GTK apps probe the Wayland socket
# in XDG_RUNTIME_DIR (the GNOME session's) and xfce4-panel segfaults in libwnck.
set -u
# shellcheck disable=SC1091
source /tmp/cua-desktop/env
export GDK_BACKEND=x11
unset WAYLAND_DISPLAY
export XDG_SESSION_TYPE=x11
export XDG_CURRENT_DESKTOP=XFCE

RUNDIR=/tmp/cua-desktop
running() { [ -f "$1" ] && kill -0 "$(cat "$1")" 2>/dev/null; }

if ! running "$RUNDIR/xfwm4.pid"; then
  setsid xfwm4 >"$RUNDIR/xfwm4.log" 2>&1 < /dev/null &
  echo $! > "$RUNDIR/xfwm4.pid"
fi
sleep 1
if ! running "$RUNDIR/panel.pid"; then
  setsid xfce4-panel >"$RUNDIR/panel.log" 2>&1 < /dev/null &
  echo $! > "$RUNDIR/panel.pid"
fi
sleep 2
if ! running "$RUNDIR/xfdesktop.pid"; then
  setsid xfdesktop >"$RUNDIR/xfdesktop.log" 2>&1 < /dev/null &
  echo $! > "$RUNDIR/xfdesktop.pid"
fi
sleep 4
for c in "xfwm4:window manager" "panel:taskbar panel" "xfdesktop:desktop"; do
  p="${c%%:*}"; label="${c#*:}"
  if running "$RUNDIR/$p.pid"; then echo "[ok] $label (pid $(cat "$RUNDIR/$p.pid"))";
  else echo "[down] $label"; fi
done
