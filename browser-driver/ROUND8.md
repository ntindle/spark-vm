# Round 8: bdrive v1 — review notes

Branch: `round8-bdrive-v1`. Not deployed. Deploy is yours (`sudo ./browser-driver/deploy.sh` from the repo root, after `jail/build.sh`).

## What it is

`bdrive` is the narrow browser-driving service: a Playwright/Chromium daemon
(`bdrived.py` + `driver.py`) on the host, a stdlib-only CLI (`bdrive`) for the
jail, a systemd unit, a deploy script, and an nftables egress table. The
agent gets exactly the v1 action set — open, goto, snapshot, click, fill,
type, press, select, check, look, get_text, wait, back, reload, state,
cookies_clear — with `completed` / `unknown` / `not_started` receipts,
ref-scoped AX refs, and automatic terminal observation after every call.
No reasoning, shell, arbitrary JS, raw CDP, or filesystem access.

## Tests

`browser-driver/test_bdrive.py` — 61/61 green (Playwright 1.62.0, real
Chromium), against a local dummy
site with dummy credentials only (`hsurr:dummy:user` / `hsurr:dummy:pass`,
never real values). One test per behavior: session open/state, every v1
action, receipts, stale-ref rejection, post-navigation rules, proxy health
gate, session expiry, password/relayed-value read masking (every typed
value is now unreadable, no caller flag — finding 75), structured
purchase approvals (session required, URL/title stamped — finding 76;
ISO timestamps — finding 77), daemon round-trip over the socket,
bad-peer rejection, empty peer-uid default (finding 73), driver
enablement gating (finding 74), `open` closing the previous page
(nit 78), daemon re-serve keeping the socket dir (finding 72), the
nftables rule file, `bdrive-firewall.service`, the `certutil` CA recipe
(finding 70), deploy.sh's nspawn-derived peer uid (nit 78), and the
confirmd `approve_action` branches including purchase (finding 79).

**Bug found by the new tests, fixed before merge:** any daemon request
that raised on the driver thread (e.g. an invalid `file_purchase_approval`)
hung read-until-EOF clients forever. `_handle` used `conn.makefile("r")`
without closing it; `makefile()` duplicates the socket fd, and the
re-raised exception's traceback kept the handler frame (and the dup'd fd)
alive in a reference cycle, so the client never saw EOF. The `bdrive` CLI
reads the same way and would have hung identically. Fixed by closing the
makefile explicitly in `_handle`; `test_file_purchase_approval_validation`
is the regression test (it hung before the fix, passes after).

## Things to know before you deploy

1. **Peer UID corrected.** The jail agent runs as guest `muse` (uid 1000),
   so with `PrivateUsers=<base>:65536` its host uid is **<base>+1000**
   (2001000 on this box), not 2000000. `deploy.sh` reads the map base
   from `/etc/systemd/nspawn/jail.nspawn` (not hardcoded) and the
   guest uid from the jail rootfs (`/var/lib/machines/jail/etc/passwd`),
   then writes a systemd drop-in (`BDRIVE_PEER_UIDS=<uid>`); it fails
   closed if the jail isn't built. The unit file's default is EMPTY
   (finding 73): a missing drop-in accepts nobody.

2. **DAC is not the peer gate.** A userns-mapped process can never carry a
   host group, so the earlier "host jail-agent user in bdrive-clients" idea
   was wrong and is gone — the group no longer exists. The socket is
   `0777` and `/run/bdrive` is `2711` by design; `SO_PEERCRED` in the
   daemon is the sole check (finding 33), applied before a single byte
   is read. Non-peers are silently dropped. Plainly: the gate
   distinguishes the jail from the host, not identities within the
   jail — anything inside the jail can become any jail uid.

3. **Driver enablement** (finding 74; spec §16): the first `open` files a
   structured `driver_enablement` request into the approvals pending dir
   and refuses until you approve it on the grant channel page. This is a
   one-time human acknowledgement that the persistent profile is in use —
   it is NOT the grant channel's first-use confirmation (that already
   covers first use of credentials via refused swaps). Approving a
   `driver_enablement` item does NOT mint a grant (there's no credential
   tuple) — `confirmd.py` instead writes
   `/home/swapd/approvals/driver-enablement-confirmed`, which the daemon
   checks.

4. **nftables** (`nftables-bdrive.nft`): explicit allow — TCP from the
   bdrive uid to 127.0.0.1:18080 — then a uid-scoped drop. No IPv6/UDP
   escape. Applied by the new `bdrive-firewall.service` oneshot at every
   boot (finding 71): it destroys the table before reloading, so a reboot
   can't regress finding 10 and re-deploy can't duplicate rules. The
   service is ordered `Before=bdrive.service`.

5. **Deploy installs**: `bdrive` user (no `bdrive-clients` group — vestigial,
   removed), a venv with pinned Playwright 1.62.0 + Chromium (the tested
   versions), the swapd CA into bdrive's NSS database with a deploy-time
   `certutil -L` check (finding 70 — Chromium ignores the system store,
   so HTTPS through the proxy needs this), profile/shots dirs, setgid
   approvals dirs (finding 50), the unit + peer drop-in, the firewall
   unit, the nspawn ordering drop-in, and the nftables rules file.
   `jail/build.sh` bind-mounts `/run/bdrive` (fail-closed: the jail won't
   start without it) and installs the CLI via `machinectl copy-to`.
   `bdrive.service` sets `RuntimeDirectoryPreserve=yes` (finding 72):
   restarts recreate only the socket file, so the jail's bind mount of
   `/run/bdrive` keeps working.

## Deferred / known limits

- `fill_card` is round 10; purchase approvals are file-only in v1.
- Snapshots are a DOM-derived AX approximation, not the true Playwright
  accessibility tree — flagged for a follow-up.
- Screenshots can show sensitive field values; AX masking is not a
  screenshot redaction. Treated as out of scope for v1 (shots dir is
  0750, bdrive-only).
- obox joins the peer list in round 9.
