#!/bin/bash
# cua-keepalive.sh (spark-vm) — keep the CUA desktop stack + bridge warm.
# Runs every 5 minutes from ntindle's crontab on spark-vm.
set -u
export PATH="/home/ntindle/cua/bin:/usr/local/bin:/usr/bin:/bin"

# Stack processes down => restart them (idempotent)
# (source the env file; executing it in a subshell would be a no-op)
# shellcheck disable=SC1091
. /tmp/cua-desktop/env 2>/dev/null || true
if ! /home/ntindle/cua/bin/cua-desktop.sh status 2>/dev/null | grep -q "\[down\]"; then
  : # all up
else
  /home/ntindle/cua/bin/cua-desktop.sh start >/dev/null 2>&1
fi

# Bridge down => restart it (localhost-only)
if ! curl -s --max-time 5 http://127.0.0.1:18731/api/status >/dev/null 2>&1; then
  setsid /home/ntindle/cua/bin/cua-bridge.py >/tmp/cua-bridge.log 2>&1 < /dev/null &
fi
