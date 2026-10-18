# Jail-lane post-build convergence (2026-10-18)

Vision-vs-state of the self-hosted agent jail's firewall lane, pinned to main
`69b9e348`, after the three builds that landed since the 2026-10-17 arch
deep-read (slot 20261017-2129): #1668 (the #1665 re-apply fix), #1673 (the
#1666 tailnet-interface validation), and #1671 (the #1655 `tenant=` on
`refused=` audit lines, from the slot-20261017-2329 security turn). Builds on the
2026-10-12 lane (#1369 stop-before-rebuild, #1371/#1370 atomic rebuilds).

**Vision (from the two deep-reads):** the self-host jail is a secure cell
whose firewall always converges to the conf on disk (rebuilds re-apply, not
just re-write), whose watchdog fails closed against a semantic pin of the
live table, whose SSH door binds only to the tailnet interface, and whose
rootfs rebuilds never silently no-op and never leave the box without a
rootfs.

## 1. Shipped claims, verified claim by claim at `69b9e348`

### F-JC-1 — #1665's fix is on main and matches its ship record (CLOSED)

The #1668 ship record said: `enable` (not `--now`) + `nft -c -f` validate +
inline destroy/`nft -f` re-apply, no unit restart. Verified in
`jail/build.sh`: L338 `systemctl enable jail-firewall.service` (no `--now`),
L352 `$SUDO nft -c -f /etc/nftables-jail.conf`, L353 `$SUDO nft destroy table
inet jail || true`, L354 `$SUDO nft -f /etc/nftables-jail.conf`, with the
comment block naming the C22 `Requires=` edge as the reason a restart is
forbidden. The README contract bullet (`jail/README.md` L105–110) matches.
`jail/test_build_smoke.py` + `test_nft_pin_canon.py`: 123 passed, 1 skipped
in this worktree at `69b9e348` — the pin suite is green on the exact base.

### F-JC-2 — #1666's fix is on main and matches its ship record (CLOSED)

The #1673 ship record said: `$JAIL_TAILNET_IF` single-sourced and validated
(shape, existence, tunnel kind, 100.64.0.0/10 address) before the conf is
written. Verified in `jail/build.sh`: L28 single-sources the variable
(default `tailscale0`), L233 shape guard, L237 existence probe, L241
tun/wireguard kind check, L245 tailnet-address check, all before the L249
sed render into `/etc/nftables-jail.conf`. The tests pin the
existence→kind→address ordering against the render
(`test_build_validates_interface_before_conf_write`,
`test_tailnet_membership_checks_pinned`). The **runtime half** of #1666 was
never claimed by #1673 — see F-JC-6.

### F-JC-3 — #1655's `tenant=` on `refused=` audit lines is on main (SHIPPED)

The #1671 ship record said: every swap-audit writer carries the `tenant=`
column, including the `refused=` family. Verified in
`proxy/swap_addon.py`: the audit-line shape doc (L168/170/181) shows
`tenant=<hint>` on `refused=hsurr:<name>`, `refused=egress`, and
`refused=authority-mismatch`, and the four audit writers (L2682/2696/2712/
3204) each carry the tenant column with the same unverified-hint caveat the
#1653 design records. Issue #1653 stays open as the design tracker; the
shipped half is the audit-line shape.

### F-JC-4 — the atomic-rebuild lane is closed for real (CLOSED)

#1370 (staging-dir swap) was closed by the owner on 2026-10-12 after #1371
shipped. Verified on main: `STAGING=/var/lib/machines/.jail-new`
(`jail/build.sh` L62), debootstrap into staging, stop, rename-swap — and
#1369's stop-before-`rm -rf` (L102 `machinectl stop $MACHINE`) is intact
under it. The closure was evidence-backed, not a Closes-keyword accident.

## 2. Still-open gaps, re-verified

### F-JC-5 — #1667 (conntrack survives a build.sh re-apply) is still open

The #1665 fix (F-JC-1) makes the *ruleset* converge on every rebuild, but the
re-apply runs with the jail up and flushes nothing: build.sh L353–354 has no
conntrack flush, and the codebase states the premise explicitly
(`jail/build.sh` L387; `jail-firewall-verify.sh` L10 and L100 — "a table
re-apply does not flush conntrack"). Established flows therefore still
survive a tightening re-apply through the `established,related` accepts.
#1667 stays open; it needs the jail-owner design decision (document / flush
/ stop-on-reapply) — this pin takes no position.

### F-JC-6 — #1672 (#1666's runtime half) is still open

#1666's build-time validation cannot see a tailnet rename/removal *after*
the build: the rules keep naming the stale interface, never match, and the
watchdog compares the unchanged table text against the pin and stays green.
The residual is stated verbatim in `jail/jail-firewall-verify.sh` L42–48,
and #1672 (filed from the #1673 review, p3) is the tracker with the fix
shape: a tick-time interface check extracting the `iifname` from the
pin/conf. #1672 stays open.

### F-JC-7 — the three #1673 review test pins are unfiled (NEW, filed this turn)

The 20261018-0029 security turn recorded three non-blocking follow-ups and
deferred them to "a future security turn"; none was filed as an issue.
Verified still true at `69b9e348`:

- (a) `test_interface_name_shape_validated` pins the shape guard's
  *existence* only — its position before the sed render is unpinned (only
  the existence guard's ordering is pinned, in
  `test_build_validates_interface_before_conf_write`).
- (b) That same test's `"JAIL_TAILNET_IF" in guard` sub-assertion is
  satisfied by the probe line itself (`/usr/sbin/ip link show
  "$JAIL_TAILNET_IF"`), not necessarily by the error message.
- (c) `_heredoc_body` is defined identically twice in
  `jail/test_build_smoke.py` (L300 and L352).

Filed as #1675 (p3, area:jail, track:open-source) — test-quality nits, no
behavioral claim.

## 3. Decisions

- **D-JC-1:** #1667's fix shape stays a jail-owner design decision; the pin
  records the open state, not a prescription.
- **D-JC-2:** #1672's prescribed fix (tick-time interface check in
  `jail-firewall-verify.sh`) stands; no design-ahead needed — the issue's
  fix shape is concrete.
- **D-JC-3:** No new architectural findings this pin. The two deep-reads plus
  four shipped builds have the lane converging; the deep-read series is
  current — the next jail turn should *build* (#1667 or #1672), not re-read.

## 4. Lane ledger

| Finding | Filed | Shipped | State at `69b9e348` |
|---|---|---|---|
| build.sh re-runs never re-apply the conf | #1665 | #1668 | Closed, verified F-JC-1 |
| SSH DNAT hardcodes `tailscale0` | #1666 | #1673 | Closed, verified F-JC-2; runtime half → #1672 |
| conntrack survives re-apply | #1667 | — | Open, verified F-JC-5 |
| refused= audit lines lack tenant= | #1655 | #1671 | Shipped, verified F-JC-3 |
| tailnet interface disappears post-build | #1672 | — | Open, verified F-JC-6 |
| atomic rebuild via staging swap | #1370 | #1371 | Closed, verified F-JC-4 |
| #1673 review test pins (a)(b)(c) | #1675 (this turn) | — | Open |
