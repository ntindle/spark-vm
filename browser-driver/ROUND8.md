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

`browser-driver/test_bdrive.py` — 39 tests, all green, against a local dummy
site with dummy credentials only (`hsurr:dummy:user` / `hsurr:dummy:pass`,
never real values). One test per behavior: session open/state, every v1
action, receipts, stale-ref rejection, post-navigation rules, proxy health
gate, session expiry, password/relayed-value read masking, structured
purchase approvals, daemon round-trip over the socket, bad-peer rejection,
first-use gating, and the confirmd first-use hook shape.

## Things to know before you deploy

1. **Peer UID corrected.** The jail agent runs as guest `muse` (uid 1000),
   so with `PrivateUsers=2000000:65536` its host uid is **2001000**, not
   2000000. `deploy.sh` computes this from the jail rootfs
   (`/var/lib/machines/jail/etc/passwd`) and writes a systemd drop-in
   (`BDRIVE_PEER_UIDS=<uid>`); it fails closed if the jail isn't built.
   The unit file's `2000000` is a placeholder default only.

2. **DAC is not the peer gate.** A userns-mapped process can never carry a
   host group, so the earlier "host jail-agent user in bdrive-clients" idea
   was wrong and is gone. The socket is `0777` and `/run/bdrive` is `2711`
   by design; `SO_PEERCRED` in the daemon is the sole check (finding 33),
   applied before a single byte is read. Non-peers are silently dropped.

3. **First-use confirmation** (spec §16): the first `open` files a
   structured `first_use` request into the approvals pending dir and
   refuses until you approve it on the grant channel page. Approving a
   `first_use` item does NOT mint a grant (there's no credential tuple) —
   `confirmd.py` instead writes `/home/swapd/approvals/first-use-confirmed`,
   which the daemon checks. That confirmd change is the one cross-round
   edit in this branch; everything else is new files plus the jail
   bind-mount/CLI provisioning in `jail/build.sh` and the `ssrf.deny`
   sudo-check nit in `proxy/deploy.sh`.

4. **nftables** (`nftables-bdrive.nft`): explicit allow — TCP from the
   bdrive uid to 127.0.0.1:18080 — then a uid-scoped drop. No IPv6/UDP
   escape.

5. **Deploy installs**: `bdrive` user, `bdrive-clients` group, a venv with
   pinned Playwright 1.62.0 + Chromium (the tested versions), profile/shots
   dirs, setgid approvals dirs (finding 50), the unit + peer drop-in, the
   nspawn ordering drop-in, and the nftables table. `jail/build.sh`
   bind-mounts `/run/bdrive` (fail-closed: the jail won't start without
   it) and installs the CLI via `machinectl copy-to`.

## Deferred / known limits

- `fill_card` is round 10; purchase approvals are file-only in v1.
- Snapshots are a DOM-derived AX approximation, not the true Playwright
  accessibility tree — flagged for a follow-up.
- Screenshots can show sensitive field values; AX masking is not a
  screenshot redaction. Treated as out of scope for v1 (shots dir is
  0750, bdrive-only).
- obox joins the peer list in round 9.
