#!/bin/bash
# fleet/gate_sync.sh — the operator sync loop (G18 §4, S1a deliverable).
#
# Iterates the estate's box list and copies the freshly published gate.json
# to each box's /var/lib/sparkvm/gate/. Run from the operator's own cron at
# <= TTL/2 (<=5 min for S1's 600s TTL): a missed loop expires the document
# by design and the fleet freezes loudly (gate-stale), rather than
# releasing itself — that is the fail-closed direction G15 §5 chose.
#
# Failure classes (§4, #1326): per-box failures are TRANSIENT by default —
# the loop warns, keeps syncing the rest of the estate, records per-box
# staleness in $ESTATE/.gate_sync_state/<box> (epoch + phase), and exits 0.
# A single down box no longer keeps the operator's cron permanently red
# (alert fatigue hid real failures inside the permanent red). Only
# estate-MISCONFIGURED boxes (an invalid ssh-target — operator data under
# local control) fail loudly with exit 1. The TTL backstop (600s default)
# bounds how long a stale box honors its last document, so the loop
# reports staleness against that bound: the record's epoch tells the
# operator whether the box is inside its TTL window or already frozen.
# The staleness record is cleared on the box's next successful sync, so
# transient outages self-heal out of the estate state.
#
# This is the delivery path that §4's latency contract names: a box holds
# the frozen document within sync_cadence of publish; effectuation completes
# within sync_cadence + tick_interval.
#
# Estate layout: one directory per box under $ESTATE (the same --estate the
# fleet inventory collector reads). Each box dir may carry an `ssh-target`
# file naming the scp destination host (default: the box dir name).
#
# Usage:
#   GATE=/path/to/gate.json ESTATE=~/fleet-estate fleet/gate_sync.sh
#   GATE=/path/to/gate.json ESTATE=~/fleet-estate fleet/gate_sync.sh --dry-run
#
# Env: GATE (required), ESTATE (required), SSH_OPTS (optional extra scp flags;
#      use it for -p <port> — ssh-target itself is restricted to plain
#      hostnames, see below), GATE_DIR (default /var/lib/sparkvm/gate),
#      GATE_USER (default root).
# The only writer of a box's gate dir is this loop (§5: delivery-path
# ownership is the cross-box forgery barrier — the MAC stops on-path
# tampering, not a rooted fleet member).
set -euo pipefail

: "${GATE:?set GATE to the published gate.json}"
: "${ESTATE:?set ESTATE to the operator estate dir}"
: "${GATE_DIR:=/var/lib/sparkvm/gate}"
: "${GATE_USER:=root}"
: "${SSH_OPTS:=}"

DRY_RUN=0
[ "${1:-}" = "--dry-run" ] && DRY_RUN=1

# One writer, enforced in code: the loop must not overlap with itself. Two
# concurrent cron ticks share nothing but the box's gate dir — §5's
# "one writer" delivery-path ownership is a per-estate property, not a
# per-PID one, so the lock is estate-scoped (single machine, single ESTATE
# path — it does not span operator machines or estate aliases). A second
# overlapping run exits loudly (exit 2) instead of racing; the fd dies with
# the process, so a killed run can never wedge future runs (flock, not a
# pidfile).
LOCKFILE="$ESTATE/.gate_sync.lock"
exec 9>"$LOCKFILE"
if ! flock -n 9; then
    echo "ERROR: another gate_sync is already syncing $ESTATE (lock $LOCKFILE held)" >&2
    exit 2
fi

fail=0        # estate-misconfigured boxes (loud fail: exit 1)
stale_count=0 # transient remote failures (warn only: exit stays 0, #1326)
synced_count=0 # boxes that received the document this run
STATE_DIR="$ESTATE/.gate_sync_state"

# _mark_stale <box> <phase>: record per-box staleness (epoch + phase) so
# the operator sees per-box staleness instead of one binary red/green.
# Advisory telemetry — a state-write failure must never turn the cron red,
# so it degrades to a warning, not a fail (#1326).
_mark_stale() {
    local box="$1" phase="$2"
    if [ "$DRY_RUN" = 1 ]; then
        return 0
    fi
    if mkdir -p "$STATE_DIR" && \
        printf '%s %s\n' "$(date -u +%s)" "$phase" > "$STATE_DIR/$box"; then
        return 0
    fi
    echo "WARNING: could not record staleness for $box (phase $phase)" >&2
    return 0
}

# _clear_stale <box>: a successful sync clears the box's staleness record —
# transient outages self-heal out of the estate state. Best-effort: the
# `|| true` keeps this fail-open on the success path — a state-dir
# pathology (permissions, STATE_DIR replaced by a file) must never turn a
# successful sync into a red cron under `set -e` (#1326).
_clear_stale() {
    local box="$1"
    if [ "$DRY_RUN" = 1 ]; then
        return 0
    fi
    rm -f "$STATE_DIR/$box" || true
    return 0
}

# _warn_transient <box> <detail>: the remote side of a box failed. The
# ssh test -d probe, scp, and install can all fail because the box is
# down — a provisioning gap (missing dir on an up box) is the same
# remote failure class. Warn, mark stale, keep syncing the rest of the
# estate. The fail-closed direction holds: the box keeps its last
# document until TTL (600s default), then freezes loudly by design.
_warn_transient() {
    local box="$1" detail="$2" phase="$3"
    echo "WARNING: $box: $detail (transient — will retry next tick; staleness recorded)" >&2
    _mark_stale "$box" "$phase"
    stale_count=$((stale_count + 1))
}

for boxdir in "$ESTATE"/*/; do
    [ -d "$boxdir" ] || continue
    box="$(basename "$boxdir")"
    if [ -f "$boxdir/ssh-target" ]; then
        target="$(head -c 256 "$boxdir/ssh-target" | tr -d '\r\n' | tr -d ' ')"
        [ -n "$target" ] || target="$box"
    else
        target="$box"
    fi
    # Estate data becomes a command line: a target that smuggles ssh/scp
    # options (e.g. "-oProxyCommand=...") is an injection, not a hostname.
    # Hostnames only here; ports and extra flags go in SSH_OPTS.
    case "$target" in
        -*|"")
            echo "ERROR: $box has an invalid ssh-target ($target)" >&2
            fail=1
            continue
            ;;
    esac
    if [[ "$target" =~ [^A-Za-z0-9._-] ]]; then
        echo "ERROR: $box has an invalid ssh-target ($target)" >&2
        fail=1
        continue
    fi
    dest="${GATE_USER}@${target}:${GATE_DIR}/gate.json"
    if [ "$DRY_RUN" = 1 ]; then
        echo "would sync $GATE -> $dest"
        continue
    fi
    # The remote gate dir must exist before we write. A failed probe is
    # the transient class: the box may be down, or the dir may genuinely
    # be unprovisioned — the loop cannot tell them apart, and both are
    # recovered by retrying next tick, not by a permanently red cron.
    # (The old "provisioning gap — fail loudly" reading of this branch
    # kept one down box red forever; #1326 moves it to warn + stale.)
    # shellcheck disable=SC2086
    if ! ssh $SSH_OPTS "${GATE_USER}@${target}" "test -d '$GATE_DIR'"; then
        _warn_transient "$box" "gate dir $GATE_DIR unreachable (box down or not provisioned)" "probe-failed"
        continue
    fi
    # Atomic, mode-preserving delivery: scp to a temp name, then install -m
    # 600 into place. The publisher's 0600 survives the trip (plain scp
    # would land the file at the remote umask), and a concurrent
    # gate_query never reads a half-written document. The tmp file is
    # removed by a remote EXIT trap, so install failures leave no litter
    # on the box (a failed scp gets a best-effort remote rm below).
    tmp_remote="$GATE_DIR/.gate.json.tmp.$$"
    # shellcheck disable=SC2086
    if ! scp $SSH_OPTS "$GATE" "${GATE_USER}@${target}:${tmp_remote}"; then
        # A failed scp can leave a partial tmp_remote behind — same litter
        # class as a failed install (the tmp name is ours, so the leftover
        # is always ours to remove). Best-effort: if the box is down this
        # ssh fails too, which is fine.
        # shellcheck disable=SC2086
        ssh $SSH_OPTS "${GATE_USER}@${target}" "rm -f '$tmp_remote'" || true
        _warn_transient "$box" "scp failed" "scp-failed"
        continue
    fi
    # The tmp file is removed by a remote EXIT trap, so an install failure
    # cleans up exactly like the success path — no .gate.json.tmp.<pid>
    # litter accumulates in the gate dir on repeated failures.
    # shellcheck disable=SC2086
    if ssh $SSH_OPTS "${GATE_USER}@${target}" \
        "trap \"rm -f '$tmp_remote'\" EXIT; install -m 600 '$tmp_remote' '$GATE_DIR/gate.json'"; then
        echo "synced $box"
        _clear_stale "$box"
        synced_count=$((synced_count + 1))
    else
        _warn_transient "$box" "atomic install failed" "install-failed"
    fi
done
echo "gate_sync done: $synced_count synced, $stale_count stale (transient), misconfigured-fail=$fail" >&2
exit "$fail"
