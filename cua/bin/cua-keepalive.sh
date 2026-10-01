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
  # Bridge log lives in the user's own ~/.cache (never world-writable
  # /tmp: a planted /tmp/cua-bridge.log symlink would get truncated by
  # the O_TRUNC open — the #493 symlink primitive — by the 5-minute
  # keepalive cron, truncating any victim-writable target as this user).
  setsid $HOME/cua/bin/cua-bridge.py 9>&- >>"$HOME/.cache/cua-bridge.log" 2>&1 < /dev/null &
fi

# Input-path wedge supervision (#769): the bridge's /api/status "input"
# field reports the XTEST keyboard-path probe verdict, but nothing ever
# refreshed it — plain /api/status is a pure read, only ?probe=1 runs the
# probe, and the liveness check above discards the body anyway. So the
# keepalive schedules a fresh probe every CUA_KEEPALIVE_PROBE_INTERVAL_S
# (default 1800 — the probe focus-hops briefly, so not every 5-minute
# tick), records each verdict in the probe history log, and tracks
# consecutive wedges in a state file that cua-desktop.sh status surfaces.
#
# Acting on the signal (restarting the desktop stack on a sustained wedge)
# stays OFF by default: the probe is new and unproven in production, so
# this only builds operational history. Setting CUA_KEEPALIVE_WEDGE_RESTART=1
# opts in: CUA_KEEPALIVE_WEDGE_THRESHOLD consecutive "wedged" verdicts
# (default 3) restart the stack once via stop+start (fresh Xvfb is the
# documented wedge remediation), with at most one restart per
# CUA_KEEPALIVE_WEDGE_COOLDOWN_S (default 3600). "ok" resets the counter;
# "unknown" (inconclusive) neither increments nor resets — the fail-safe
# direction per #492.
# shellcheck disable=SC2120 # tests (cua/test_shell_scripts.py) call
# input_probe_check with [state_dir] [bridge_url] overrides; the
# production call site passes none.
input_probe_check() { # input_probe_check [state_dir] [bridge_url]
  local state_dir=${1:-$HOME/.cache}
  local bridge=${2:-http://127.0.0.1:18731}
  local state_file="$state_dir/cua-input-probe.state"
  local hist_file="$state_dir/cua-input-probe.log"
  local now; now=$(date +%s)
  local interval=${CUA_KEEPALIVE_PROBE_INTERVAL_S:-1800}
  local threshold=${CUA_KEEPALIVE_WEDGE_THRESHOLD:-3}
  local cooldown=${CUA_KEEPALIVE_WEDGE_COOLDOWN_S:-3600}
  case "$interval" in ''|*[!0-9]*) interval=1800 ;; esac
  case "$threshold" in ''|*[!0-9]*|0) threshold=3 ;; esac
  case "$cooldown" in ''|*[!0-9]*) cooldown=3600 ;; esac
  local last_check=0 consecutive=0 last_state=unknown last_restart=0
  if [ -f "$state_file" ]; then
    # The state file is written by this function only; still, parse
    # defensively — a hand-edited or half-written file must not inject
    # anything into the shell.
    while IFS='=' read -r k v; do
      case "$k" in
        last_check) case "$v" in ''|*[!0-9]*) ;; *) last_check=$v ;; esac ;;
        consecutive_wedged) case "$v" in ''|*[!0-9]*) ;; *) consecutive=$v ;; esac ;;
        last_restart) case "$v" in ''|*[!0-9]*) ;; *) last_restart=$v ;; esac ;;
        last_state) case "$v" in ok|wedged|unknown|unparseable) last_state=$v ;; esac ;;
      esac
    done < "$state_file"
  fi
  if [ "$((now - last_check))" -lt "$interval" ]; then
    return 0
  fi
  if ! command -v python3 >/dev/null 2>&1; then
    echo "cua-keepalive: python3 missing — skipping input-probe check" >&2
    return 0
  fi
  local body
  if ! body=$(curl -s --max-time 15 "$bridge/api/status?probe=1" 2>/dev/null) \
      || [ -z "$body" ]; then
    # Bridge unreachable: the liveness block above owns that case —
    # don't double-act on a probe that never ran.
    echo "cua-keepalive: input probe fetch failed (bridge down?)" >&2
    return 0
  fi
  local verdict
  verdict=$(printf '%s' "$body" | python3 -c \
    'import json,sys
try:
    print(json.load(sys.stdin).get("input", {}).get("state", "unknown"))
except Exception:
    print("unparseable")' 2>/dev/null) || verdict=unparseable
  case "$verdict" in
    wedged) consecutive=$((consecutive + 1)) ;;
    ok) consecutive=0 ;;
    *) ;; # unknown/unparseable: inconclusive — leave the counter alone
  esac
  last_state=$verdict
  printf '%s %s consecutive=%s\n' "$now" "$verdict" "$consecutive" >>"$hist_file"
  local gate=${CUA_KEEPALIVE_WEDGE_RESTART:-0}
  if [ "$gate" = "1" ] && [ "$verdict" = "wedged" ] \
      && [ "$consecutive" -ge "$threshold" ] \
      && [ "$((now - last_restart))" -ge "$cooldown" ]; then
    echo "cua-keepalive: input path wedged ${consecutive}x consecutively; restarting desktop stack" >&2
    # 9>&-: see above — the restarted stack must not inherit the run lock.
    "$HOME/cua/bin/cua-desktop.sh" stop 9>&- >/dev/null 2>&1
    "$HOME/cua/bin/cua-desktop.sh" start 9>&- >/dev/null 2>&1
    last_restart=$now
    consecutive=0
  fi
  local tmp
  tmp=$(mktemp "$state_dir/.cua-input-probe.state.XXXXXX") || return 0
  {
    printf 'last_check=%s\n' "$now"
    printf 'last_state=%s\n' "$last_state"
    printf 'consecutive_wedged=%s\n' "$consecutive"
    printf 'last_restart=%s\n' "$last_restart"
  } >"$tmp"
  mv -f "$tmp" "$state_file"
}

# Input-path wedge supervision (#769): schedule the probe on a ~30-minute
# cadence, record the history, and (opt-in) restart on a sustained wedge.
input_probe_check
