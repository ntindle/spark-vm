# Trust & transparency

The trust story of a persistent computer for an agent, stated plainly:
what we promise, what the architecture actually enforces, and what we
own as residual risk. Every vendor claim below was read on a vendor page
(section 2 carries the read date); every spark-vm claim points at the
code that enforces it.

## The one-paragraph version

Your persistent computer is a real VM, not a mounted folder. The agent
gets its own machine — its own filesystem, its own user, its own
network rules — and nothing inside that machine is a window onto the
host. Host folders are never shared into it. Credentials are swapped at
the network edge by a proxy the agent can't see around, so the agent
never holds the raw materials. Approvals are human-gated. The rest of
this document is the evidence for those sentences.

## Why this matters: the Docker Sandboxes escape week

In September 2026, Docker Sandboxes shipped two guest→host escapes —
the week's loudest object lesson in what "a microVM plus a mounted host
folder" costs when the folder boundary fails. Facts, read on
[Docker's own release notes](https://docs.docker.com/ai/sandboxes/release-notes/)
(2026-09-19; the page is the vendor's live source and these lines may be
edited by Docker at any time):

- **CVE-2026-77179**: *"Fixed CVE-2026-77179, a symlink vulnerability in
  the virtio-fs host server on macOS that could let a malicious guest
  read or modify arbitrary host files outside the shared workspace,
  potentially leading to code execution on the host."* Fixed in **0.42.0**
  (released 2026-09-07).
- **CVE-2026-79994**: *"Fixed CVE-2026-79994, a symlink race in the
  guest-to-host Unix domain socket relay that could let a malicious
  guest connect to arbitrary host Unix sockets outside the shared
  workspace, exposing data or host-side capabilities."* Same fix
  release, 0.42.0.
- The same 0.42.0 notes close two more sandbox-boundary vulnerabilities
  with no CVE attached: *"Fixed a vulnerability where a sandboxed
  process could get the daemon to open a host D-Bus transport and
  execute an arbitrary command on the host."* and *"Fixed a
  vulnerability where a malicious sandbox could hijack another sandbox's
  OAuth login by pre-claiming its callback port."*
- Both CVEs were disclosed on 2026-09-15, **eight days after the fix
  shipped** in 0.42.0. Disclosure note: earlier reads of this same page
  (2026-09-17) found neither CVE named; Docker has since amended the
  notes to name both verbatim. The version number is the signal —
  release-note prose lagged the fix, and the fix preceded the CVE.

The architectural fact underneath, also from Docker's own docs
([architecture page](https://docs.docker.com/ai/sandboxes/architecture/)):
`sbx run` still defaults to mounting the current directory into the
sandbox "through a filesystem passthrough" — the sandbox sees your
actual host files. That shared-workspace boundary is the trust story of
a persistent-computer product, and this week proved how fragile the
"microVM + mounted host folder" model is when the passthrough has a
symlink bug.

**What spark-vm takes from this:** the boundary both CVEs broke — a
shared host folder the guest can see — does not exist in our reference
architecture. There is no passthrough to have a symlink bug in.

## What spark-vm does differently

The reference deployment (Owner decision 2, `jail/README.md`) puts the
agent's SSH login inside a persistent **systemd-nspawn container** that
mirrors the agent's runtime cell (`jail/cell-mirror.md`):

- **No host folders, ever.** `jail/build.sh` carries the deliberate
  decision: *"Deliberately no bind mounts: no host files inside the
  jail."* The `[Files]` section of the `.nspawn` file contains only
  `PrivateUsersOwnership` — nothing is shared in. (`jail/README.md`:
  "**No host secrets/state/logs inside.** No bind mounts. Placeholders
  only."; `jail/cell-mirror.md`: "no swapd-readable paths mounted in,
  placeholders only".)
- **Guest root is not host root.** `PrivateUsers=2000000:65536` maps
  container uid 0 to host uid 2000000 — a container escape still lands
  in an unprivileged host uid. (`PrivateUsers=yes` was deliberately
  rejected: on a fresh debootstrap it can silently yield an identity
  map. See `jail/README.md` for the verification command.)
- **The jail cannot reach the host network.** An nftables table
  (`table inet jail`, priority −10) DNATs only the proxy ports and the
  tailnet→jail SSH forward; every other packet originating from the
  jail's veth is dropped — internet, tailnet, and host services alike.
  The firewall, not the route table, is the enforcement.
- **No DNS in the jail.** `/etc/resolv.conf` is empty; name resolution
  happens in the host proxy, where the SSRF guard runs. Direct egress
  is dead by design.
- **swapd, the audit log, and the confirmation page live on the host** —
  never in the jail. The jail never holds a real secret, only
  `hsurr:` placeholders.

So the Docker escape-week attack class — guest exploits a shared-folder
passthrough to reach host files — has no corresponding surface here.
The Docker D-Bus class (guest → management daemon → host command) is
the class we watch instead, and it's addressed below as an owned risk,
not a solved one.

## What we do not claim (owned risks)

Plainly, because a trust doc that only lists wins is marketing copy:

1. **The management-plane boundary still exists.** The jail is a
   container, not a hardware VM. A kernel or nspawn escape class still
   exists; uid-mapping narrows its blast radius but doesn't delete it.
   We track this the way the week taught everyone to: the boundary is
   the product, and it gets re-examined when the ecosystem learns
   something new (this document exists because of that habit).
2. **The D-Bus class is ours too.** Docker's D-Bus fix is a
   guest→daemon→host path. Our jail's deliberate host exposures are
   exactly two: the proxy ports (DNATed, audited) and the SSH relay
   (tailnet only). Those are allowlisted, not shared folders — but they
   are surfaces, and any finding against them lands here as a finding,
   not a footnote.
3. **Multi-tenancy is future work.** The OAuth-port-claim class —
   one sandbox attacking another's login flow — has no spark-vm analog
   today because there is one tenant per box. A hosted spark-vm with
   many tenants *will* have cross-tenant surfaces; the multi-tenancy
   audit (H11) gates the hosted design on answering them. We do not
   claim hosted trust properties for a product that isn't built yet.
4. **The guarantee is scoped to the jail architecture.** A plain-box
   self-host deployment (no jail) has no guest→host boundary because
   the agent's computer *is* the box — the trust boundary is between
   the box and the rest of the operator's network, and the agent runs
   with the box user's privileges. Know which shape you're running.
5. **The agent trusts swapd for TLS.** The swapd CA is installed in the
   jail's trust store so HTTPS inspection works; the agent is expected
   to notice that its "secure" connections terminate at a proxy. That
   is deliberate and disclosed: the point of the proxy is substitution
   of placeholders, not secrecy from the operator. The audit journal
   (`swap.log`) is the check on the proxy, and it names placeholders,
   never values.
6. **The sentinel is not shipped.** Per `docs/POSITIONING.md`'s
   anti-claims: the sentinel is the unbuilt half of the trust story.
   This document describes what exists.

## Verify it yourself

Every claim above is checkable on a deployed box. The full verify
block is in `jail/README.md`; the short version:

```bash
# the jail really has no host mounts
systemd-nspawn --machine=jail ... # or: inspect /etc/systemd/nspawn/jail.nspawn [Files]
grep -c 'Bind' /etc/systemd/nspawn/jail.nspawn   # expect 0
# guest root is not host root
machinectl shell root@jail /bin/sh -c 'cat /proc/1/uid_map'  # expect 0 2000000 65536
# direct egress is dead from inside the jail
ssh -p 2222 muse@<tailnet-ip> 'curl -s --max-time 8 -o /dev/null -w "%{http_code}\n" https://example.com || echo BLOCKED'
```

## Freshness

- Vendor facts in the escape-week section were read on
  `docs.docker.com` on **2026-09-19** (Docker Sandboxes release notes,
  0.42.0, released 2026-09-07; architecture page). Re-check them when
  Docker publishes; this document's job is to move when the ecosystem
  does.
- spark-vm claims are code-verified against the cited files at this
  commit. If a cited line moves, the claim moves with it — file an
  issue if you catch drift.
