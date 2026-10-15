#!/bin/bash
# pair-tick-wrapper.sh — D-RW5 unenrolled-skip gate for the golden-image
# pairing programs (#1219, #1274).
#
# Modes:
#   pair-tick-wrapper.sh loop <interval-secs> <client> [<client-arg>...]
#       Tick loop (heartbeat, rotate): invokes the client every <interval>
#       seconds. While the box is unenrolled the client invocation is
#       skipped and the loop sleeps quietly each tick.
#   pair-tick-wrapper.sh daemon <client> [<client-arg>...]
#       Daemon shape (phone-home): sleep-polls (with backoff) until the box
#       is enrolled, then execs the daemon. D-RW3's exit-code mapping
#       (exit 0 = clean stop, 1 = human-attention, 2 = crash -> restart)
#       applies to the daemon proper, never to this pre-enrollment gate —
#       a bare daemon would exit 1 pre-redeem, an expected death under
#       autorestart=unexpected + exitcodes=0,1, and could never re-arm
#       post-redeem (the exact composition D-RW5 warned against).
#
# "Enrolled" = enrollment.json present in the client state dir. The dir
# mirrors spark_pair.py::_state_dir minus the --dir flag: $SVM_PAIR_DIR,
# else $HOME/.config/spark-pair (supervisord sets HOME=/home/sparkpair).
#
# Once-loud-then-quiet (D-RW5): exactly one loud block at wrapper start
# naming the manual `redeem` step; after that the gate stays quiet until
# enrollment lands. Per-tick loudness at 1/min would spam supervisord logs
# for the whole pre-redeem window.
#
# Failure visibility (A4): a persistently failing tick is invisible to
# supervisord by design — the loop never exits on tick failure (cron
# semantics: the next tick retries). Tick-failure detail is the client
# state-dir's append-only failure logs; their 1 MiB single-generation
# bounding is in-code (D21, #1020 — landed).
#
# Test seams (documented, test-only): PAIR_WRAPPER_MAX_TICKS makes `loop`
# exit 0 after N ticks; PAIR_WRAPPER_BACKOFF_BASE sets the daemon poll's
# initial backoff seconds (default 5; fractional values keep a fixed
# cadence instead of doubling — the test seam).
set -u

WRAPPER="pair-tick-wrapper"
STATE_DIR="${SVM_PAIR_DIR:-${HOME:?pair-tick-wrapper: HOME must be set}/.config/spark-pair}"
ENROLL="$STATE_DIR/enrollment.json"

loud_once() {
    echo "$WRAPPER: no enrollment.json in $STATE_DIR — this box is not yet paired."
    echo "$WRAPPER: complete the manual redeem step, then the pairing runtime starts on its own:"
    echo "$WRAPPER:   sudo -u sparkpair python3 /opt/sparkvm/pairing/spark_pair.py --dir $STATE_DIR redeem"
    echo "$WRAPPER: ticks stay quiet until enrollment lands (D-RW5 once-loud-then-quiet)."
}

mode_loop() {
    local interval="$1"; shift
    local ticks=0 loud=0
    local max_ticks="${PAIR_WRAPPER_MAX_TICKS:-0}"
    while true; do
        if [ -f "$ENROLL" ]; then
            # Cron semantics: a failed tick exits the one-shot, never the loop.
            "$@" || true
        elif [ "$loud" -eq 0 ]; then
            loud_once
            loud=1
        fi
        ticks=$((ticks + 1))
        if [ "$max_ticks" -gt 0 ] && [ "$ticks" -ge "$max_ticks" ]; then
            exit 0
        fi
        sleep "$interval"
    done
}

mode_daemon() {
    local base="${PAIR_WRAPPER_BACKOFF_BASE:-5}"
    local wait="$base"
    if [ ! -f "$ENROLL" ]; then
        loud_once
        while [ ! -f "$ENROLL" ]; do
            sleep "$wait"
            case "$wait" in
                *.*) ;;  # fractional test seam: fixed cadence
                *) wait=$((wait * 2)); [ "$wait" -gt 300 ] && wait=300 ;;
            esac
        done
    fi
    exec "$@"
}

case "${1:-}" in
    loop)   shift; [ "$#" -ge 2 ] || { echo "$WRAPPER: usage: $0 loop <interval-secs> <client> [args...]" >&2; exit 2; }; mode_loop "$@" ;;
    daemon) shift; [ "$#" -ge 1 ] || { echo "$WRAPPER: usage: $0 daemon <client> [args...]" >&2; exit 2; }; mode_daemon "$@" ;;
    *) echo "$WRAPPER: usage: $0 {loop <interval-secs>|daemon} <client> [args...]" >&2; exit 2 ;;
esac
