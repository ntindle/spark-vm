#!/bin/bash
# jail-firewall-verify.sh — runtime watchdog for `table inet jail` (C25).
#
# Fail-closed: the jail must not keep running on damaged enforcement.
# The verify timer (jail-firewall-verify.timer, every 5 minutes) runs this
# service. The checked invariant is the enforcement rules themselves, not
# the chain shells: all three chains are `policy accept`, so an emptied
# chain (e.g. `nft flush chain inet jail forward`) is open egress — the
# watchdog pins the drop-rule markers and the proxy DNAT rule — and pins the
# allow head too: every accept/dnat verdict in the live table must be one
# of the expected narrow rules, because with policy-accept chains a WIDENED
# ruleset (an added broad accept above the drops) voids the isolation
# exactly like a deleted drop, and marker presence alone cannot see it.
#
# On confirmed damage: stop the jail FIRST (a table re-apply does not flush
# conntrack, so hole-era flows would survive repair via the
# established,related accept rule), then repair the table. Every
# fail-closed event exits nonzero so the unit goes red — the operator
# restarts the jail explicitly. Successful repair is therefore never
# "green and quiet".
set -uo pipefail

# Overridable for tests (functional tests stub `nft` via this variable and
# `systemctl`/`logger`/`sleep` via PATH).
NFT="${NFT:-/usr/sbin/nft}"
CONF=/etc/nftables-jail.conf
TABLE="inet jail"

list_rules() { "$NFT" list table "$TABLE" 2>/dev/null; }

# The enforcement markers the isolation depends on: the three drop rules
# (log prefixes are the rules' fingerprints in `nft list` output) and the
# proxy DNAT. All must be present.
healthy() {
    local rules="$1"
    printf '%s' "$rules" | grep -q 'jail-fwd-drop' \
    && printf '%s' "$rules" | grep -q 'jail-fwd-indrop' \
    && printf '%s' "$rules" | grep -q 'jail-input-drop' \
    && printf '%s' "$rules" | grep -q 'dnat to 127.0.0.1' \
    && allow_head_intact "$rules"
}

# Allow-head pin: with policy-accept chains, an ADDED broad accept (or an
# added/altered DNAT) above the drop rules voids the isolation exactly like
# a deleted drop — but the marker presence checks above cannot see a
# WIDENED ruleset. Every verdict-bearing rule in the live table must
# therefore be one of the expected lines: the two DNATs and the four narrow
# accepts. Anything else fails closed. (The build-time twin of this pin is
# test_build_smoke.py::TestIsolation::test_nftables_accept_head_is_proxy_and_ssh_only.)
allow_head_intact() {
    local rules="$1" line t
    while IFS= read -r line; do
        t="${line#"${line%%[![:space:]]*}"}"   # ltrim
        case "$t" in
            chain*|type*|table*|"}"*|"") continue ;;
        esac
        # DNAT verdicts: the proxy DNAT must end at 127.0.0.1 exactly —
        # a port-suffixed (dnat to 127.0.0.1:9999) or re-addressed
        # (dnat to 127.0.0.10) variant still contains the marker
        # substring, so only the end-anchored form passes.
        case "$t" in
            *"dnat to 127.0.0.1") ;;
            *"dnat ip to 10.99.0.2:22") ;;
            *dnat*) return 1 ;;
        esac
        # Accept verdicts: each must contain one of the narrow allow
        # fingerprints (full match expression included, so a broader rule
        # cannot smuggle the fingerprint along). Trailing statements after
        # the terminal accept verdict cannot widen, so these stay
        # unanchored; the DNAT forms above stay end-anchored where
        # trailing text changes the meaning.
        case "$t" in
            *"tcp dport { 18080, 18081 } accept"*|\
            *"ct state established,related accept"*|\
            *"tcp dport 22 ct state new,established accept"*) ;;
            *accept*) return 1 ;;
        esac
    done <<< "$rules"
    return 0
}

rules="$(list_rules)" || rules=""
if healthy "$rules"; then
    exit 0
fi
# Transient tolerance: the oneshot jail-firewall.service's own
# destroy-then-apply is a millisecond-scale hole. Re-check once before
# treating it as damage; a repair-in-progress heals, real damage persists.
sleep 10
rules="$(list_rules)" || rules=""
if healthy "$rules"; then
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
