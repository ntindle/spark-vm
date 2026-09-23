#!/bin/bash
# jail-firewall-verify.sh — runtime watchdog for `table inet jail` (C25).
#
# Fail-closed: the jail must not keep running on damaged enforcement.
# The verify timer (jail-firewall-verify.timer, every 5 minutes) runs this
# service. The checked invariant is the enforcement rules themselves, not
# the chain shells: all three chains are `policy accept`, so an emptied
# chain (e.g. `nft flush chain inet jail forward`) is open egress — the
# watchdog pins the drop-rule markers and the proxy DNAT rule — and pins
# the allow head too: every rule line in the live table must be one of the
# installed conf's rule lines, matched on the FULL rule text (match
# expression and verdict), because with policy-accept chains a WIDENED
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
# `systemctl`/`logger`/`sleep` via PATH; CONF is stubbed the same way).
NFT="${NFT:-/usr/sbin/nft}"
CONF="${CONF:-/etc/nftables-jail.conf}"
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

# Normalize one ruleset line for comparison: left-trim, then drop headers
# (table/chain/type/closing brace), comments and blank lines — those carry
# no rule. Quoted strings are stripped (log prefixes, comments) so
# expected text cannot hide inside attacker-controlled quotes. Prints the
# normalized line; returns nonzero for lines that carry no rule.
norm_rule_line() {
    local t="${1#"${1%%[![:space:]]*}"}"   # ltrim
    case "$t" in
        ""|"#"*|chain*|type*|table*|"}"*) return 1 ;;
    esac
    printf '%s' "$t" | sed 's/"[^"]*"//g'
}

# The expected rule lines: every rule in the installed conf, normalized.
# The conf is the single source of truth (build.sh renders it with the
# real JAIL_SSH_PORT); nothing about the allow head is hardcoded here, so
# the pin cannot drift from the table it guards.
conf_rule_lines() {
    local line n
    while IFS= read -r line; do
        if n="$(norm_rule_line "$line")"; then
            [ -n "$n" ] && printf '%s\n' "$n"
        fi
    done < "$CONF"
}

# Allow-head pin: with policy-accept chains, an ADDED broad rule (or an
# added/altered DNAT) above the drop rules voids the isolation exactly
# like a deleted drop — but the marker presence checks above cannot see a
# WIDENED ruleset. Every rule line in the live table must therefore be one
# of the conf's rule lines, matched on the FULL rule text (match
# expression plus verdict). A broadened match (a dropped iifname, daddr or
# dport qualifier) or an altered DNAT target ('dnat to 127.0.0.1:9999',
# 'dnat to 127.0.0.10') is not the expected line and fails closed — and a
# verdict the conf never uses ('redirect', 'fwd', 'masquerade', ...) fails
# closed the same way. Exact matching is safe because any conf change IS
# the new truth. An unreadable conf fails closed too: the watchdog must
# not bless a table it cannot compare.
# (The build-time twin of this pin is
# test_build_smoke.py::TestIsolation::test_nftables_accept_head_is_proxy_and_ssh_only.)
allow_head_intact() {
    local rules="$1" line t expected
    expected="$(conf_rule_lines)" || expected=""
    [ -n "$expected" ] || return 1
    while IFS= read -r line; do
        t="$(norm_rule_line "$line")" || continue
        [ -n "$t" ] || continue
        printf '%s\n' "$expected" | grep -qxF -- "$t" || return 1
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
