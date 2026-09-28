#!/bin/bash
# cua-keepalive.sh (spark-vm) — keep the CUA desktop stack + bridge warm.
# Runs every 5 minutes from the agent user's crontab on spark-vm.
set -u
export PATH="$HOME/cua/bin:/usr/local/bin:/usr/bin:/bin"

# Shared env-file trust predicate (#493) — the same check every consumer
# of the desktop env file applies.
# shellcheck disable=SC1091
. "$(dirname "${BASH_SOURCE[0]}")/cua-trust.sh"

# Serialize the whole run (#495): two overlapping keepalive invocations
# (slow box, cron skew) can both fail the bridge health probe and both
# spawn the bridge, which is the double-spawn vector. A contended
# invocation just exits — the holder does the whole check-and-start.
# The lock lives in the user's own $HOME/.cache (never world-writable
# /tmp: a planted symlink there would get truncated by the O_TRUNC open
# below — #493's sibling — and any local user could squat the lock).
# Returns 0 when the lock is held, 2 when another run holds it (not an
# error), 1 when the lock cannot be acquired at all (loud failure).
# shellcheck disable=SC2120 # tests (cua/test_shell_scripts.py) call take_run_lock
# with a lockfile arg override; the production call site passes none.
take_run_lock() { # take_run_lock [lockfile] — arg override exists for tests
  local lock=${1:-$HOME/.cache/cua-bridge.keepalive.lock}
  mkdir -p "$(dirname "$lock")" 2>/dev/null || {
    echo "cua-keepalive: cannot create lock dir for $lock" >&2
    return 1
  }
  if ! exec 9>"$lock"; then
    echo "cua-keepalive: cannot open run lock $lock" >&2
    return 1
  fi
  if ! flock -n 9; then
    echo "cua-keepalive: another keepalive run holds the lock; exiting" >&2
    return 2
  fi
}
rc=0
take_run_lock || rc=$?
[ "$rc" -eq 2 ] && exit 0          # another run is doing the work
[ "$rc" -eq 0 ] || exit 1          # lock failure is fatal and loud

# The env file lives in world-writable /tmp and sourcing executes it as
# this user (#493). Source it only if it passes the shared trust check;
# otherwise proceed without it.
# shellcheck disable=SC2120 # tests (cua/test_shell_scripts.py) call safe_source_env
# with an env-file arg override; the production call site passes none.
safe_source_env() { # safe_source_env [env_file] — arg override exists for tests
  local f=${1:-/tmp/cua-desktop/env}
  trust_env_file "$f" || return 1
  # shellcheck disable=SC1090,SC1091
  . "$f"
}
safe_source_env || true

# Stack processes down => restart them (idempotent). A status probe that
# fails outright or prints nothing (e.g. the rundir guard refusing an
# untrusted stack) counts as DOWN — never as "all up".
status_out=""
if ! status_out=$($HOME/cua/bin/cua-desktop.sh status 2>&1); then
  echo "cua-keepalive: status probe failed, treating stack as down: $status_out" >&2
  status_out="[down]"
fi
if [ -z "$status_out" ] || printf '%s\n' "$status_out" | grep -q "\[down\]"; then
  # 9>&-: the run lock above lives on fd 9's open file description, and
  # flock is held by every process inheriting the fd. Closing fd 9 in the
  # spawned stack keeps the daemons from pinning the lock after this run
  # exits (without it, the first spawn would silently disable every future
  # keepalive run). No-op when fd 9 is not open (manual runs).
  $HOME/cua/bin/cua-desktop.sh start 9>&- >/dev/null 2>&1
fi

# Bridge down => restart it (localhost-only)
if ! curl -s --max-time 5 http://127.0.0.1:18731/api/status >/dev/null 2>&1; then
  # 9>&-: see above — the bridge must not inherit the run lock.
  setsid $HOME/cua/bin/cua-bridge.py 9>&- >/tmp/cua-bridge.log 2>&1 < /dev/null &
fi
