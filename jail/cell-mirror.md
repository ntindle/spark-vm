# How Muse's own cell works — notes for the spark-vm nspawn jail

Owner decision 2 (2026-09-15) asks for this: a description of how the
agent's own runtime cell treats **package installs** and **egress
approvals**, gathered the same interview way Spec v2 was, so the
systemd-nspawn jail for the agent login can mirror it. Facts below are
what I can observe from inside my cell plus the product docs shipped
with it (`~/docs/`); inferences are marked.

## What the cell is

- My shell reports `whoami=root`. That root is **cell root, not host
  root**: the credential boundary lives outside the cell. The Secure
  Vault holds raw values where I cannot read them; I only ever see
  opaque references (`[credential:<uuid>]`), and a separate delivery
  path (`authd`) puts values directly into browser controls. Being root
  inside the cell buys no access to the vault. The jail wants exactly
  this property: guest root is not host root, and no host secrets,
  swapd state, bdrive state, or audit log exist inside.
- The cell is **replaceable without warning**. I have watched the host
  get swapped mid-task (`/usr/bin/docker` gone, uptime reset).
  Everything outside my workspace (`~/workspace`, the one persistent
  directory) is ephemeral: `/tmp`, pip site-packages, `/usr/local/bin`
  installs, running daemons. The jail should assume the same: anything
  not in a bound volume or rebuilt from this repo can vanish, so the
  jail must be rebuildable from the repo, not hand-tended.

## Package installs

- `apt-get install`, `pip install`, `npm install` all work, as root,
  with **no per-install approval step**. Installing software is an
  ordinary action; the approval model (below) gates *sensitive or
  state-changing* actions, not package management.
- Install traffic egresses through the runtime's HTTP(S) proxy
  (`https_proxy`/`HTTPS_PROXY` env, credentials embedded — never
  echoed). There is no direct internet.
- Cell-specific limits I have hit, worth mirroring as "the jail will
  have its own quirks, document them": the kernel lacks
  iptables/NAT modules, so `dockerd` only runs with
  `--iptables=false --ip-masq=false --bridge=none` and containers need
  `--network host`; overlayfs fails, so the `vfs` storage driver is
  required. Lesson for the jail: decide up front what the container
  runtime inside the jail may do, and write it down (see Docker below).
- Because installs are ephemeral (see above), anything the jail needs
  after a rebuild must come from the repo or a package manager, never
  from a hand-installed binary someone remembers.

**Mirror:** package installs free inside the jail (rootful inside, own
rootfs), egress for installs routed through the host swap proxy like
all other jail egress, no approval gate on installs, and a documented
rebuild path (REVIEW finding 19) so nothing depends on box state.

## Egress

- **All egress goes through the runtime's proxy.** Shell, curl, python
  all use it. It is HTTP CONNECT, TCP only: no UDP, no ping, no
  MagicDNS (I resolve tailnet names to IPs myself). There is no
  general-purpose direct route out.
- Opening a *new kind* of tunnel can itself require approval: the
  Tailscale notes shipped with my runtime say tunnel connections may
  trigger a user approval each time. So the cell distinguishes
  *using* an approved egress path (no prompt) from *establishing* a new
  one (prompt). The jail's analog: the veth-to-swap-proxy path is the
  approved path; anything else (a second interface, a hole punched for
  one job) is a new path and should need the human.
- DNS: I do my own resolution for what I need; the proxy CONNECTs by
  hostname. For the jail, note that the swap proxy resolves the request
  host itself on the host (that is where finding 29's SSRF guard runs),
  so the jail's applications do not need working DNS of their own for
  HTTP — but anything in the jail that dials IPs directly bypasses the
  guard, which is why the veth must have no route except the proxy.

**Mirror:** the jail's veth has exactly one egress — the swap proxy on
the host. No direct internet, no second interface without a human
decision. swapd on the host is where host allowlists, the SSRF guard,
and per-credential bindings are enforced.

## Approvals (the allowlist and approval model)

- **Ordinary tasks need no approval.** Sensitive or state-changing
  actions do: logging in, purchases, posting, sending mail. An ordinary
  browser form submit is currently allowed by default.
- **Purchases never get a standing allow.** Every purchase needs fresh
  approval, every time, by design. Email sends are the same. A
  scheduled task that sends mail can hold a narrow standing allow
  scoped to that one task, removable by the user. This is the shape the
  jail should copy: the allowlist (`hosts.allow`) is the standing
  approval for *where* a credential may go; *spending money* or other
  irreversible acts always go back to the human.
- **The approval channel is out-of-band by construction.** Approvals go
  to the client UI — "not via their conversation with Muse" — and the
  answer routes directly back. I cannot see the approval card's layout
  or buttons, cannot promise which choice stops future prompts, and
  cannot approve on the user's behalf. Owner decision 3 (the tailnet
  page, authenticated by Tailscale identity, answered only by the human,
  with nothing routed through obox or the orchestrator) is the faithful
  mirror of this: the jail's sensitive actions must bottom out at a
  human-created signal the agent cannot forge.
- **One-time credential delivery needs fresh one-time approval.**
  A one-time code from connected mail/messages reaches me only as an
  opaque reference; `authd` holds it briefly in memory and delivers it
  directly to the browser *after a fresh approval*, then consumes it. I
  never see the value. The spark-vm analog already exists in miniature:
  the one-time-code relay is the stated exception in owner decision 6,
  and the card pathway (job-scoped, expiring, merchant-bound
  placeholders, deleted at job end) is the general mechanism.
- **Standing grants are listed and user-revocable.** The permissions
  page lists every standing permission; I can see only pending
  approvals, and I cannot revoke or change a grant — the user does that.
  The jail should keep the same split: swapd/bdrive can report what is
  granted; only the human changes it.
- **Everything is recorded.** Every action of mine lands in the
  Activity view and approvals History; none of it can be secretly
  erased. Owner decision 5 keeps the swapd audit log on the box as the
  verification aid — the jail's sensitive crossings (swapd swaps,
  bdrive confirmations, tailnet-page answers) should all be observable
  there, on the host, outside the jail.

## Credentials

- Entered only through approved capture flows, stored outside the
  cell, never in my memory/files/logs. `cred set` in the user's own SSH
  session is already the aligned analog (REVIEW: "Credential capture UI
  on the client routes straight to authd" → "Aligned").
- The jail must not change this: no secret material inside the jail's
  rootfs, no swapd-readable paths mounted in, placeholders only.

## SSH: how the login lands in the jail (review round 2)

Two workable shapes; the choice decides where the host keys and the
ControlMaster socket live:

1. **sshd inside the jail**, bound to the veth address, with the host
   forwarding the tailnet port (socat/iptables REDIRECT or a small
   forwarder) into the container. The jail then owns its own host keys
   (generated at build, stored in the jail rootfs), and my SSH client
   config points at the tailnet address as today. The ControlMaster
   socket lives on my side, unchanged.
2. **The host's sshd, with a per-user forced command** (or a
   `Match User` block) that enters the container
   (`machinectl shell` / `systemd-run --machine=`). Host keys stay on
   the host; the jail has no sshd at all. Simpler key story, but every
   login pays the enter-container hop, and the forced command must be
   exactly right or the login lands on the host.

Either is fine. What is not fine is the agent's interactive SSH
landing on the host by accident: the jail boundary has to be the
default, not a directory the agent remembers to cd into.

## Persistence: the jail is not the cell

My cell is replaced without warning; installs vanish and that is a
*property* ("everything free but ephemeral"). This box is a workhorse
and the jail should be **persistent**: the rootfs lives on disk,
package installs and build state survive reboots. Keep "rebuildable
from the repo" as the property instead — the jail's build (nspawn
unit, veth wiring, proxy-only egress, installed packages) is
reproducible from `spark-vm`, so a corrupted jail is a rebuild, not a
mystery. Do not mirror the cell's disposability; mirror its
*rebuildability*.

## Docker

Owner decision 2 names it: Docker is a host escape if the jail can
reach the host socket. In my cell, Docker-in-cell is crippled by the
missing kernel modules anyway; the jail has a real kernel available,
so be explicit: **podman inside the container, or no container runtime
at all** — never a mount of the host's `/var/run/docker.sock`.
Rootless Docker needs nested user namespaces and subuid/subgid
ranges inside the container, which is fiddly under nspawn; podman is
the likelier path and should be budgeted as an experiment, not assumed.

Related, and worth stating plainly: anything in the jail that dials
IPs directly or needs UDP will not work by design — no ping, no
`git` over SSH, no DNS beyond the proxy's resolver. Git goes over
HTTPS through `with-proxy`, as `push.sh` already does.

## What this does not cover

Meta-internal details I cannot see (how the proxy authenticates me,
how authd is implemented) are deliberately absent — the mirror is
about the *properties* (cell root ≠ host root; credentials outside;
approvals out-of-band and unforgeable by the agent; everything
audited; installs free and the jail rebuildable from the repo), not
the mechanism.
