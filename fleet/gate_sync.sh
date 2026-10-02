#!/bin/bash
# fleet/gate_sync.sh — the operator sync loop (G18 §4, S1a deliverable).
#
# Iterates the estate's box list and copies the freshly published gate.json
# to each box's /var/lib/sparkvm/gate/. Run from the operator's own cron at
# <= TTL/2 (<=5 min for S1's 600s TTL): a missed loop expires the document
# by design and the fleet freezes loudly (gate-stale), rather than
# releasing itself — that is the fail-closed direction G15 §5 chose.
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
# Env: GATE (required), ESTATE (required), SSH_OPTS (optional extra scp flags),
#      GATE_DIR (default /var/lib/sparkvm/gate), GATE_USER (default root).
# The only writer of a box's gate dir is this loop (§5: delivery-path
# ownership is the cross-box forgery barrier — the MAC stops on-path
# tampering, not a rooted fleet member).
set -euo pipefail

: "${GATE:?set GATE to the published gate.json}"
: "${ESTATE:?set ESTATE to the operator's estate dir}"
: "${GATE_DIR:=/var/lib/sparkvm/gate}"
: "${GATE_USER:=root}"
: "${SSH_OPTS:=}"

DRY_RUN=0
[ "${1:-}" = "--dry-run" ] && DRY_RUN=1

fail=0
for boxdir in "$ESTATE"/*/; do
    [ -d "$boxdir" ] || continue
    box="$(basename "$boxdir")"
    if [ -f "$boxdir/ssh-target" ]; then
        target="$(head -c 256 "$boxdir/ssh-target" | tr -d '\r\n' | tr -d ' ')"
        [ -n "$target" ] || target="$box"
    else
        target="$box"
    fi
    dest="${GATE_USER}@${target}:${GATE_DIR}/gate.json"
    if [ "$DRY_RUN" = 1 ]; then
        echo "would sync $GATE -> $dest"
        continue
    fi
    # The remote gate dir must exist and be root-owned before we write:
    # a missing dir is a provisioning gap, not a sync gap — fail loudly.
    # shellcheck disable=SC2086
    if ssh $SSH_OPTS "${GATE_USER}@${target}" \
        "test -d '$GATE_DIR' && install -m 600 /dev/null '$GATE_DIR/.gate-write-probe' && rm '$GATE_DIR/.gate-write-probe'"; then
        # shellcheck disable=SC2086
        if scp $SSH_OPTS "$GATE" "$dest"; then
            echo "synced $box"
        else
            echo "ERROR: scp to $box failed" >&2
            fail=1
        fi
    else
        echo "ERROR: $box has no writable $GATE_DIR (provision it first: G18 §5)" >&2
        fail=1
    fi
done
exit "$fail"
