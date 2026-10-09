#!/bin/bash
# proxy/ensure-approval-filer.sh — idempotent enrollment of a filing
# principal in the confirmd pending/ shared group (issue #1174).
#
# proxy/deploy.sh §4e provisions the dedicated `approval-filers` group
# (`root:approval-filers 2770` on <CONFIRM_DIR>/pending, issue #1167) and
# enrolls swapd unconditionally, but could only enroll bdrive if the user
# already existed — no repo step provisions the bdrive user yet (it is
# still a hardening-plan account). This snippet extracts that enrollment
# so both callers share it: the deploy calls it for swapd and bdrive, and
# the future bdrive-provisioning (box hardening) step must call it at
# user-creation time, so bdrive is never stranded with EACCES on pending/
# for want of group membership (fail-closed would show no bdrive-filed
# items and swaps would stay refused until the next proxy deploy).
#
# Idempotent: safe to run when the group is absent (creates it) or the
# user is absent (no-op, still exits 0). Invoke with privilege, e.g.
#   sudo proxy/ensure-approval-filer.sh approval-filers bdrive
# (deploy.sh runs its privileged steps via sudo itself; this script
# embeds no sudo).
#
# Security note: never expose this helper via a sudoers rule with an
# argument wildcard — arbitrary <group> <user> as root would let a
# less-privileged caller enroll anyone anywhere.
set -euo pipefail

group="${1:?usage: $0 <group> <user>}"
user="${2:?usage: $0 <group> <user>}"

if ! getent group "$group" >/dev/null; then
    # Race-tolerant: a concurrent deploy/hardening step may win the
    # groupadd; re-check before failing.
    groupadd -r "$group" 2>/dev/null || {
        getent group "$group" >/dev/null || {
            echo "ERROR: could not create group '$group'" >&2
            exit 1
        }
    }
fi
if id -u "$user" >/dev/null 2>&1; then
    usermod -aG "$group" "$user"   # no-op when already enrolled
    echo "ensure-approval-filer: enrolled '$user' in group '$group'"
else
    # The user does not exist yet (bdrive until the hardening step lands);
    # not an error — the hardening step re-runs this at user creation.
    # Drift-class notice goes to stderr (repo convention).
    echo "ensure-approval-filer: user '$user' absent, nothing to do" >&2
fi
