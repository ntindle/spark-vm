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
# - Tailnet-interface rename/removal after the build was pin-invisible
#   (issue #1666's runtime half, closed by #1672): the rules keep
#   referencing the build-time interface name, so the SSH DNAT silently
#   never matches again while the pin compares unchanged table text and
#   stays green. The tick-time tailnet_interface_problem check below
#   closes it: the interface the conf binds the SSH DNAT to must exist
#   and carry a 100.64.0.0/10 address on every tick, failing closed like
#   table damage. Fresh-boot grace (TAILNET_BOOT_GRACE_SECS): tailscaled
#   may come up after the firewall unit, so an absent interface inside
#   the grace is transient, not divergence.
set -uo pipefail

# Overridable for tests (functional tests stub `nft` via this variable,
# `python3` resolves from PATH, and `systemctl`/`logger`/`sleep` via
# PATH; PIN and CANON are stubbed the same way; IP is stubbed the same
# way for the tailnet-interface check; BOOT_SECS overrides the
# boot-grace clock).
NFT="${NFT:-/usr/sbin/nft}"
IP="${IP:-/usr/sbin/ip}"
CONF="${CONF:-/etc/nftables-jail.conf}"
PIN="${PIN:-/etc/nftables-jail.pin.json}"
CANON="${CANON:-/usr/local/sbin/jail-nft-pin-canon.py}"
TABLE="inet jail"
# 100.64.0.0/10 — twin of build.sh's #1666 tailnet-address guard (keep
# the two in sync).
TAILNET_ADDR_RE='inet 100\.(6[4-9]|[78][0-9]|9[0-9]|1[01][0-9]|12[0-7])\.'
# Fresh-boot grace for the tailnet-interface check (issue #1672):
# tailscaled may come up after the firewall unit on a fresh boot, so an
# absent interface inside this window is transient, not divergence —
# the next ticks re-check.
TAILNET_BOOT_GRACE_SECS=600

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

# Seconds since boot, for the fresh-boot grace. Fails closed: if the
# clock is unreadable we assume a long-up box (no grace).
boot_seconds() {
    if [ -n "${BOOT_SECS:-}" ]; then
        printf '%s' "$BOOT_SECS"
        return 0
    fi
    if [ -r /proc/uptime ]; then
        awk '{print int($1)}' /proc/uptime
    else
        printf '999999999'
    fi
}

# Tick-time tailnet-interface check (issue #1672 — the #1666 runtime
# half). build.sh validates $JAIL_TAILNET_IF at build time only; a
# post-build rename or removal (tailscaled restart with a different
# --tun-interface, tailscaled down, logout) leaves the nft rules
# referencing a stale name that silently never matches, while the
# semantic pin compares unchanged table text and stays green.
#
# Extracts the iifname the conf binds the jail's SSH DNAT to and
# requires it to exist AND carry a 100.64.0.0/10 address. Prints the
# divergence description and returns 1 on divergence; returns 0 when
# healthy — and when the interface is absent inside the fresh-boot
# grace (tailscaled may not be up yet; the next ticks re-check). A
# conf with no iifname at all is out of scope here: the pin governs
# table structure.
#
# Extraction anchors on the SSH DNAT specifically: the template's
# FIRST iifname line is the proxy DNAT's "ve-jail"
# (dnat ip to 127.0.0.1), so a bare "first iifname" grab watches the
# wrong interface and would fail-closed on every healthy box (Security
# round-1 blocker). The SSH DNAT is the dnat rule whose target is not
# the proxy loopback.
tailnet_interface_problem() {
    local ifname
    ifname="$(sed -n '/dnat ip to 127\.0\.0\.1/!s/.*iifname "\([^"]*\)".*dnat ip to .*/\1/p' "$CONF" 2>/dev/null | head -n 1)"
    [ -z "$ifname" ] && return 0
    if ! "$IP" link show dev "$ifname" >/dev/null 2>&1; then
        if [ "$(boot_seconds)" -lt "$TAILNET_BOOT_GRACE_SECS" ]; then
            logger -t jail-firewall-verify \
                "note: tailnet interface '$ifname' absent $(boot_seconds)s after boot (inside ${TAILNET_BOOT_GRACE_SECS}s grace) — tailscaled may not be up yet; staying green this tick"
            return 0
        fi
        printf "tailnet interface '%s' is gone (renamed or removed after the build); the SSH DNAT silently never matches" "$ifname"
        return 1
    fi
    if ! "$IP" -o -4 addr show dev "$ifname" 2>/dev/null | grep -qE "$TAILNET_ADDR_RE"; then
        if [ "$(boot_seconds)" -lt "$TAILNET_BOOT_GRACE_SECS" ]; then
            logger -t jail-firewall-verify \
                "note: tailnet interface '$ifname' has no 100.64.0.0/10 address $(boot_seconds)s after boot (inside ${TAILNET_BOOT_GRACE_SECS}s grace) — tailscaled may not be up yet; staying green this tick"
            return 0
        fi
        printf "tailnet interface '%s' exists but carries no 100.64.0.0/10 address" "$ifname"
        return 1
    fi
    return 0
}

# Fail-closed funnel shared by table damage and tailnet-interface
# divergence: stop the jail FIRST (a table re-apply does not flush
# conntrack, so hole-era flows would survive repair via the
# established,related accept rule), then repair the table. Every
# fail-closed event exits nonzero so the unit goes red — the operator
# restarts the jail explicitly. Successful repair is therefore never
# "green and quiet".
fail_closed() {
    local reason="$1"
    # NOTE: no ${2:-default} here — a ' inside the :- word opens a quote
    # context in bash and swallows the rest of the line.
    local hint="${2:-}"
    if [ -z "$hint" ]; then
        hint="restart is the operator's explicit decision"
    fi
    logger -t jail-firewall-verify \
        "ALERT: $reason — fail-closed: stopping jail, then repairing table"

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
        "REPAIRED: table $TABLE re-applied; jail stopped fail-closed — $hint"
    # Red unit on every fail-closed event: the operator must see that the
    # jail was stopped, even when the repair itself succeeded.
    exit 1
}

if healthy; then
    # Table intact — the #1672 runtime check: the interface the SSH DNAT
    # binds to must still exist with its tailnet address.
    problem="$(tailnet_interface_problem)" && exit 0
    # Transient tolerance: a tailscaled restart is a seconds-scale gap.
    # Re-check once before treating it as divergence; a restart heals,
    # a rename/removal persists.
    sleep 10
    if problem="$(tailnet_interface_problem)"; then
        logger -t jail-firewall-verify \
            "note: tailnet interface gap healed without repair"
        exit 0
    fi
    fail_closed "tailnet interface divergence: $problem" \
        "fix the tailnet interface, then re-run jail/build.sh (it re-validates the interface and regenerates the pin); restart is the operator's explicit decision"
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

fail_closed "table $TABLE enforcement damaged"
