# The agent jail

Owner decision 2 (2026-09-15): the agent's SSH login lands in a
persistent systemd-nspawn container, mirroring the agent's own runtime
cell (see `cell-mirror.md`). swapd, bdrive, the audit log, and the
confirmation page live on the host.

## Architecture

```
                        tailnet (100.65.241.20)
                        |
   agent SSH ---------->| :2222 --DNAT--> jail sshd :22 (user muse)
   human SSH ---------->| :22 (host sshd, user ntindle)
   human browser ------>| :8443 confirmd (Tailscale-identity auth)
                        |
                        v
              +---------------------+
              | host (spark-vm)     |
              |  swapd, bdrive      |
              |  swap.log (audit)   |
              |  127.0.0.1:18080/81 |  <-- mitmdump, unchanged config
              +---------------------+
                        ^  DNAT (nftables, table inet jail)
                        |  10.99.0.1:18080/18081 -> 127.0.0.1:18080/18081
              +---------------------+
              | jail (nspawn)       |
              |  10.99.0.2/30       |
              |  user muse, sshd    |
              |  proxy env ->       |
              |    10.99.0.1:18080  |
              |  swapd CA in system |
              |  trust store        |
              |  NO dns, NO direct  |
              |  egress, NO host    |
              |  mounts             |
              +---------------------+
```

## Guarantees

- **Guest root is not host root.** `PrivateUsers=yes`: the container
  runs in a user namespace; uid 0 inside maps to an unprivileged host
  range.
- **Proxy-only egress.** nftables `table inet jail` (priority -10, so
  it runs before Docker/Tailscale chains):
  - jail -> 10.99.0.1:18080/18081 is DNATed to the host proxy;
  - every other packet originating from `ve-jail` is dropped —
    including to the tailnet, the internet, and host services
    (the jail cannot SSH to the host);
  - tailnet :2222 is DNATed to the jail's sshd. Nothing else is
    forwarded in.
- **No host secrets/state/logs inside.** No bind mounts at all
  (`[Files]` is empty). Placeholders only.
- **No DNS.** `/etc/resolv.conf` is empty in the guest; name
  resolution happens in the host proxy (mitmproxy CONNECTs by
  hostname, where finding 29's SSRF guard runs). Anything dialing IPs
  directly or needing UDP — ping, git-over-SSH — does not work by
  design. Git goes over HTTPS through `with-proxy`.
- **swapd CA trusted system-wide inside the jail only.**
  Everything in the jail is meant to go through the proxy, so the CA
  is installed with `update-ca-certificates` in the guest. After the
  jail exists, the CA is removed from the host store (below).
- **Persistent, rebuildable.** The rootfs lives at
  `/var/lib/machines/jail`; `machinectl enable jail` starts it at
  boot. Everything about it is produced by `jail/build.sh` in this
  repo — a corrupted jail is a rebuild (`build.sh --rebuild-rootfs`),
  not a mystery.

## Build

On the host, as ntindle:

```bash
~/spark-vm/jail/build.sh
```

What it does, in order: installs `systemd-container`+`debootstrap`;
bootstraps Ubuntu 24.04 (noble) to `/var/lib/machines/jail`;
writes `/etc/systemd/nspawn/jail.nspawn`; installs the
`jail-firewall` oneshot unit (`/etc/nftables-jail.conf`,
`Before=systemd-nspawn@jail.service`); adds the host veth address
drop-in; enables and starts the machine; configures the guest
(static `host0` 10.99.0.2/30, empty resolv.conf, proxy env + apt
proxy, openssh-server, `muse` user with the agent's SSH key,
passwordless sudo inside the jail, swapd CA, jail `with-proxy`).

Verify:

```bash
# agent login lands in the jail
ssh -p 2222 muse@100.65.241.20 'hostname; id -un'
# proxy works from the jail
ssh -p 2222 muse@100.65.241.20 'with-proxy curl -s -o /dev/null -w "%{http_code}\n" https://example.com'
# direct egress is dead
ssh -p 2222 muse@100.65.241.20 'curl -s --max-time 8 -o /dev/null -w "%{http_code}\n" https://example.com || echo BLOCKED'
# host is unreachable from the jail
ssh -p 2222 muse@100.65.241.20 'curl -s --max-time 8 telnet://100.65.241.20:22 || echo BLOCKED'
# DNS fails fast
ssh -p 2222 muse@100.65.241.20 'getent hosts example.com || echo NO-DNS'
```

## Removing the swapd CA from the host (after the jail verifies)

Owner decision 5: trust the CA system-wide inside the jail only.

1. The host's `with-proxy` needs its own bundle first (it points at
   the system store today):
   ```bash
   sudo mkdir -p /usr/local/share/with-proxy-ca
   sudo sh -c 'cat /etc/ssl/certs/ca-certificates.crt \
       /home/swapd/.mitmproxy/mitmproxy-ca-cert.pem \
       > /usr/local/share/with-proxy-ca/ca-bundle.crt'
   ```
   then point `CA_BUNDLE` in `/usr/local/bin/with-proxy` at
   `/usr/local/share/with-proxy-ca/ca-bundle.crt`.
2. Remove from the host store and refresh:
   ```bash
   sudo rm /usr/local/share/ca-certificates/swapd-mitmproxy.crt
   sudo update-ca-certificates
   ```
3. Confirm: `with-proxy curl https://example.com` still works on the
   host; `trust list | grep -i swapd` (or openssl verify against the
   system bundle) no longer shows it.

Nothing on the host needs the CA in the system store afterwards:
swapd reads its own CA files, host apt/ssh/tailscaled never go
through the proxy, and Chromium uses its NSS database.

## Files

- `build.sh` — the reproducible build (run on the host).
- `cell-mirror.md` — how the agent's own cell works; the properties
  the jail mirrors.
- `confirm-page.md` — confirmation page design; the answer→grant
  channel is specified but not implemented (owner review required).
