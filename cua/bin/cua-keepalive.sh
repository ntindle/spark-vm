#!/bin/bash
# cua-keepalive.sh (spark-vm) — keep the CUA desktop stack + bridge warm.
# Runs every 5 minutes from the agent user's crontab on spark-vm.
set -u
export PATH="$HOME/cua/bin:/usr/local/bin:/usr/bin:/bin"

# Serialize the whole run (#495): two overlapping keepalive invocations
# (slow box, cron skew) can both fail the bridge health probe and both
# spawn the bridge, which is the double-spawn vector. A contended
# invocation just exits — the holder does the whole check-and-start.
exec 9>/tmp/cua-bridge.keepalive.lock
flock -n 9 || exit 0

# The env file lives in world-writable /tmp and sourcing executes it as
# this user (#493). Source it only if it is a regular file, owned by us,
# and not writable by group/other; otherwise proceed without it.
safe_source_env() { # safe_source_env [env_file] — arg override exists for tests
  local f=${1:-/tmp/cua-desktop/env}
  [ -f "$f" ] && [ ! -L "$f" ] || return 1
  [ "$(stat -c %U "$f")" = "$(id -un)" ] || return 1
  [ $(( 0$(stat -c %a "$f") & 022 )) -eq 0 ] || return 1
  # shellcheck disable=SC1091
  . "$f"
}
safe_source_env || true

# Stack processes down => restart them (idempotent)
if ! $HOME/cua/bin/cua-desktop.sh status 2>/dev/null | grep -q "\[down\]"; then
  : # all up
else
  $HOME/cua/bin/cua-desktop.sh start >/dev/null 2>&1
fi

# Bridge down => restart it (localhost-only)
if ! curl -s --max-time 5 http://127.0.0.1:18731/api/status >/dev/null 2>&1; then
  setsid $HOME/cua/bin/cua-bridge.py >/tmp/cua-bridge.log 2>&1 < /dev/null &
fi
