#!/bin/bash
# jail-firewall-verify.sh — runtime watchdog for `table inet jail` (C25).
#
# Fail-closed: the jail must not keep running on damaged enforcement.
# The verify timer (jail-firewall-verify.timer, every minute) runs this
# service. The checked invariant is the enforcement rules themselves, not
# the chain shells: all three chains are `policy accept`, so an emptied
# chain (e.g. `nft flush chain inet jail forward`) is open egress — the
# watchdog pins the whole table semantically and, on confirmed damage,
# stops the jail FIRST (a table re-apply does not flush conntrack, so
# hole-era flows would survive repair via the established,related accept
# rule), then repairs the table. Every fail-closed event exits nonzero so
# the unit goes red — the operator restarts the jail explicitly.
# Successful repair is therefore never "green and quiet".
#
# Semantic pin (issue #444): build.sh captures `nft --json list table
# inet jail` right after applying the conf and stores the canonicalized
# capture at /etc/nftables-jail.pin.json. At tick time this script
# captures the live table through the SAME canonicalizer
# (jail-nft-pin-canon.py: nftables-version metainfo, kernel handles and
# volatile counter readings stripped; dict keys sorted) and requires
# byte equality. Both sides are rendered by the same nft binary's JSON
# renderer, so whitespace AND semantic text re-renderings (the #436/#444
# class — e.g. `ct state established,related` as `ct state {
# established, related }`) are absorbed instead of fail-closing. A
# damaged table (deleted drop, added broad accept, re-addressed DNAT)
# differs structurally from the pin and fails closed.
#
# Stated residuals of the semantic pin:
# - JSON schema drift: a future nft whose JSON schema re-words the table
#   structurally (fields the canonicalizer does not know) diffs the pin
#   and fails closed — on the first post-upgrade tick, by design; the
#   fix is re-running build.sh, which regenerates the pin. The
#   build-time self-test (build.sh runs this service once after
#   capturing the pin) trips a canonicalizer *crash* on this box's
#   rendering, not drift — it cannot see a re-wording that has not
#   happened yet.
# - Hand-editing /etc/nftables-jail.conf without re-running build.sh no
#   longer trips the watchdog (the live table still matches the pin).
#   The conf is still the repair source: make table changes through
#   build.sh, which regenerates the pin from the applied conf.
set -uo pipefail

# Overridable for tests (functional tests stub `nft` via this variable,
# `python3` resolves from PATH, and `systemctl`/`logger`/`sleep` via
# PATH; PIN and CANON are stubbed the same way).
NFT="${NFT:-/usr/sbin/nft}"
CONF="${CONF:-/etc/nftables-jail.conf}"
PIN="${PIN:-/etc/nftables-jail.pin.json}"
CANON="${CANON:-/usr/local/sbin/jail-nft-pin-canon.py}"
TABLE="inet jail"

# Capture the live table through the canonicalizer. Prints the canonical
# JSON on stdout; returns nonzero on any failure (nft error, missing
# canon helper, invalid JSON) so the caller fails closed.
capture_table() {
    "$NFT" --json list table "$TABLE" 2>/dev/null | python3 "$CANON" 2>/dev/null
}

# The build-time expected table, re-canonicalized on read (idempotent —
# tolerates a pin file that was stored un-canonicalized).
read_pin() {
    python3 "$CANON" < "$PIN" 2>/dev/null
}

# Semantic pin comparison: live == pin, both canonicalized. An unreadable
# pin, a failed capture, or any structural difference is damage —
# fail closed, never bless an unverifiable table.
healthy() {
    local live pin
    live="$(capture_table)" || return 1
    pin="$(read_pin)" || return 1
    [ -n "$live" ] && [ -n "$pin" ] && [ "$live" = "$pin" ]
}

if healthy; then
    exit 0
fi
# Transient tolerance: the oneshot jail-firewall.service's own
# destroy-then-apply is a millisecond-scale hole. Re-check once before
# treating it as damage; a repair-in-progress heals, real damage persists.
sleep 10
if healthy; then
    logger -t jail-firewall-verify \
        "note: transient table gap healed without repair"
    exit 0
fi

logger -t jail-firewall-verify \
    "ALERT: table $TABLE enforcement damaged — fail-closed: stopping jail, then repairing table"

# Stop first: re-applying the table does not flush conntrack, so any flow
# the jail opened while unenforced would keep passing the
# established,related accept rule after repair. Stopping the container
# tears down its veth and its flows with it.
if ! systemctl stop systemd-nspawn@jail; then
    logger -t jail-firewall-verify \
        "CRITICAL: could not stop jail after enforcement damage"
fi

# Validate before destroying: a corrupt conf must not widen the hole.
if ! "$NFT" -c -f "$CONF"; then
    logger -t jail-firewall-verify \
        "CRITICAL: $CONF failed validation — table left as-is; jail stopped, operator must intervene"
    exit 1
fi
"$NFT" destroy table "$TABLE" 2>/dev/null
if ! "$NFT" -f "$CONF"; then
    logger -t jail-firewall-verify \
        "CRITICAL: re-apply of table $TABLE FAILED — jail stopped, operator must intervene"
    exit 1
fi

logger -t jail-firewall-verify \
    "REPAIRED: table $TABLE re-applied; jail stopped fail-closed — restart is the operator's explicit decision"
# Red unit on every fail-closed event: the operator must see that the
# jail was stopped, even when the repair itself succeeded.
exit 1
