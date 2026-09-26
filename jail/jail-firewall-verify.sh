#!/bin/bash
# jail-firewall-verify.sh — runtime watchdog for `table inet jail` (C25).
#
# Fail-closed: the jail must not keep running on damaged enforcement.
# The verify timer (jail-firewall-verify.timer, every minute) runs this
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
    && printf '%s' "$rules" | grep -q 'dnat ip to 127.0.0.1' \
    && allow_head_intact "$rules"
}

# Normalize one ruleset line for comparison: left-trim, then drop headers
# (table/chain/type/closing brace), comments and blank lines — those carry
# no rule. Lines are compared with quotes INTACT: quoted identifiers
# (interface names, log prefixes) are part of the rule's identity —
# stripping them would make iifname "ve-jail" and iifname "tailscale0"
# indistinguishable. Full-line exact matching leaves nowhere for a
# smuggled fingerprint to hide. Prints the normalized line; returns
# nonzero for lines that carry no rule.
norm_rule_line() {
    local t="${1#"${1%%[![:space:]]*}"}"   # ltrim
    case "$t" in
        ""|"#"*|chain*|type*|table*|"}"*) return 1 ;;
    esac
    printf '%s\n' "$t"
}

# Canonicalize a normalized rule line for comparison: strip ALL whitespace
# outside double-quoted segments (issue #436). The watchdog pins `nft list`
# output text, and nft's formatter is version-dependent (brace spacing,
# indent width, token gaps); whitespace-only differences carry no rule
# semantics, but a naive full-text match turns a formatter change into a
# false fail-closed — the jail stopped every minute for nothing, training
# the operator to ignore the red unit this component was built to produce.
# Quoted segments (interface names, log prefixes, DNAT targets) are left
# INTACT: stripping inside them would make iifname "ve-jail" and
# iifname "tailscale0" indistinguishable (the IFACE_SWAP regression).
# Residual (known, not absorbed): semantic re-renderings a formatter could
# introduce, e.g. `ct state established,related` as
# `ct state { established, related }`. The build-time self-test does NOT
# cover that class: it catches deploy-time conf-vs-renderer skew (the
# authoring side), but an nft upgrade AFTER the build that re-renders
# semantically still false-fail-closes on the first watchdog tick.
# Tracked as issue #444 (semantic pin design: `nft --json` capture at
# build time, compared with the same renderer at tick time).
norm_canon() {
    local rest="$1" out="" pre seg
    while [[ "$rest" == *\"* ]]; do
        pre="${rest%%\"*}"          # up to the first quote
        seg="${rest#*\"}"           # after the first quote
        out+="${pre//[[:space:]]/}"
        if [[ "$seg" == *\"* ]]; then
            out+="\"${seg%%\"*}\""
            rest="${seg#*\"}"
        else
            # Unbalanced quote: cannot occur from nft/conf output; keep the
            # tail verbatim (whitespace-stripped) rather than guessing.
            out+="\"${seg//[[:space:]]/}"
            rest=""
        fi
    done
    out+="${rest//[[:space:]]/}"
    printf '%s' "$out"
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
# dport qualifier) or an altered DNAT target ('dnat ip to 127.0.0.1:9999',
# 'dnat ip to 127.0.0.10') is not the expected line and fails closed — and a
# verdict the conf never uses ('redirect', 'fwd', 'masquerade', ...) fails
# closed the same way. Matching is safe because any conf change IS
# the new truth. An unreadable conf fails closed too: the watchdog must
# not bless a table it cannot compare.
# The comparison is on CANONICALIZED lines (norm_canon), not the raw
# `nft list` text: whitespace-only formatter variance (indent, brace
# spacing, token gaps) carries no rule semantics and must not fail the pin
# (issue #436). Quoted segments stay intact so interface-name and
# log-prefix identity survive canonicalization.
# (The build-time twin of this pin is
# test_build_smoke.py::TestIsolation::test_nftables_accept_head_is_proxy_and_ssh_only.)
allow_head_intact() {
    local rules="$1" line t canon expected canon_expected
    expected="$(conf_rule_lines)" || expected=""
    [ -n "$expected" ] || return 1
    # Canonicalize the expected set once (both sides go through the same
    # norm_rule_line -> norm_canon pipeline).
    canon_expected="$(while IFS= read -r line; do
        t="$(norm_rule_line "$line")" || continue
        [ -n "$t" ] || continue
        norm_canon "$t"
        printf '\n'
    done <<< "$expected")"
    while IFS= read -r line; do
        t="$(norm_rule_line "$line")" || continue
        [ -n "$t" ] || continue
        canon="$(norm_canon "$t")"
        printf '%s\n' "$canon_expected" | grep -qxF -- "$canon" || return 1
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
