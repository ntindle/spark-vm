# Trust & transparency

The trust story of a persistent computer for an agent, stated plainly:
what we promise, what the architecture actually enforces, and what we
own as residual risk. Every vendor claim below was read on a vendor page
(section 2 carries the read date); every spark-vm claim points at the
code that enforces it.

## The one-paragraph version

Your persistent computer is a real machine, not a mounted folder. The
agent gets its own machine — its own filesystem, its own user, its own
network rules — and nothing inside that machine is a window onto the
host. In the jail architecture, host folders are never shared into the
agent's machine. Credentials are swapped at the network edge by a proxy
the agent can't see around, so the agent never holds the raw materials.
Approvals are human-gated. The rest of this document is the evidence
for those sentences.

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
  shipped** in 0.42.0 (reported by third-party security press, e.g.
  [The Hacker News](http://thehackernews.com/2026/09/critical-docker-sandboxes-flaw-lets.html);
  the CVE records themselves were not readable on cve.org directly at
  write time). Disclosure note: third-party reads found the 0.42.0
  notes named neither CVE as of 2026-09-17 (same article); read directly
  on docs.docker.com on 2026-09-19, the notes now name both verbatim.
  The version number is the signal — release-note prose lagged the fix,
  and the fix preceded the CVE.
- Third-party press credited Oren Yomtov of accomplish.ai with finding
  CVE-2026-77179 and Jurre van Bergen of ThreatNotify with finding
  CVE-2026-79994.

The architectural fact underneath, also from Docker's own docs
([architecture page](https://docs.docker.com/ai/sandboxes/architecture/)):
`sbx run` still defaults to mounting the current directory into the
sandbox "through a filesystem passthrough" — the sandbox sees your
actual host files. Two qualifications, because a trust doc can't afford
selective contrast: since 0.42.0, `sbx create` can omit the workspace
path entirely ("the sandbox has no host workspace bind mount"), and
Docker sandboxes are hypervisor-isolated microVMs — a *stronger*
isolation primitive than our OS container (see owned-risk #1 below).
But the passthrough default was the default when both CVEs shipped,
and `sbx run` still mounts the current directory. That shared-workspace
boundary is the trust story of a persistent-computer product, and this
week proved how fragile the "microVM + mounted host folder" model is
when the passthrough has a symlink bug.

**What spark-vm takes from this:** the two CVEs are different classes.
CVE-2026-77179's class — a shared-workspace *filesystem passthrough*
with a symlink bug — has no analog in the jail: there is no passthrough
to break. CVE-2026-79994's class — a host *relay* (guest-to-host Unix
socket path validation) — maps directly onto spark-vm's own
deliberately exposed relay surfaces: the DNATed proxy ports and the
tailnet SSH forward. Those are owned as a surface in risk #2, not
claimed away.

## What spark-vm does differently

The committed architecture (Owner decision 2, `jail/README.md`) — not
yet the default deployment, which is still a plain box — puts the
agent's SSH login inside a persistent **systemd-nspawn container** that
mirrors the agent's runtime cell (`jail/cell-mirror.md`):

- **No host folders, ever.** `jail/build.sh` carries the deliberate
  decision: *"Deliberately no bind mounts: no host files inside the
  jail."* The `[Files]` section of the `.nspawn` file carries a single
  key — `PrivateUsersOwnership` — nothing is shared in.
  (`jail/README.md`: "**No host secrets/state/logs inside.** No bind
  mounts. Placeholders only."; `jail/cell-mirror.md`: "no swapd-readable
  paths mounted in, placeholders only".) One future exception is on the
  record: `browser-driver/REVIEW.md` plans for `bdrive`'s *socket*
  (not a folder) to be bind-mounted into the jail, SO_PEERCRED-gated to
  the jail's mapped uid. The day that ships, it becomes the deliberate
  exception to this bullet.
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

So the CVE-2026-77179 class — guest exploits a shared-folder
passthrough to reach host files — has no corresponding surface in the
jail. The Docker D-Bus class and the CVE-2026-79994 socket-relay class
(guest → host relay → host capabilities) are the classes we watch
instead, and they're addressed below as owned risks, not solved ones.

## What we do not claim (owned risks)

Plainly, because a trust doc that only lists wins is marketing copy:

1. **The management-plane boundary still exists.** The jail is a
   container, not a hardware VM. A kernel or nspawn escape class still
   exists; uid-mapping narrows its blast radius but doesn't delete it.
   We track this the way the week taught everyone to: the boundary is
   the product, and it gets re-examined when the ecosystem learns
   something new (this document exists because of that habit).
2. **The D-Bus class and the -79994 relay class are ours too.**
   Docker's D-Bus fix is a guest→daemon→host path; CVE-2026-79994 is a
   guest→host-relay path-validation bug. Our jail's deliberate host
   exposures are exactly two: the proxy ports (DNATed, audited) and the
   SSH relay (tailnet only). Those are allowlisted, not shared folders —
   but they are surfaces, and any finding against them lands here as a
   finding, not a footnote.

   **Relay audit (2026-09-20, the -79994 / D-Bus class against the two
   exposures + the planned bdrive socket bind-mount).** The class in
   CVE-2026-79994 is a *path-validation race*: the guest steers a
   host-side relay toward an arbitrary host socket by swapping a path
   (symlink) between the relay's check and its connect
   (characterization per the escape-week section above — release notes
   read 2026-09-19).
   Applied to our exposures:

   - **Proxy relay (jail → mitmdump).** `jail/build.sh` DNATs
     `iifname "ve-jail" ip daddr 10.99.0.1 tcp dport { 18080, 18081 }`
     to host `127.0.0.1`; the nftables `input` chain accepts those
     two dports from `ve-jail` (plus established/related return legs)
     and drops everything else — including every other 127.0.0.1
     port (so `route_localnet=1` on `ve-jail`, finding 51, cannot be
     used to reach loopback services like cred-ui's tunnel). Honest
     caveat on the bound: the port-accept rule itself carries no daddr
     match, so the jail can open 18080/18081 on *any* host address, not
     just 127.0.0.1 — harmless in practice because mitmdump listens
     only on 127.0.0.1, but the rules do not state the tighter bound.
     The
     relay target is a fixed IP:port pair — there is no path, no
     symlink, nothing guest-influenced to race. The -79994 mechanism
     has no target here: nothing about the relay can be redirected.
     What the jail *can* do through it is bounded by the listener:
     mitmdump with `--set listen_host=127.0.0.1` and no web UI
     (`proxy/swap-proxy.service`, `proxy/swap-inference.service`). If
     swapd's services stop, the relay fails closed (nothing listens).
     The real frontier is therefore not the relay but the proxy's own
     handling — e.g. #92 (SSE bodies bypass response scrubbing) and
     #94 (open-redirect on an allowlisted host) are proxy bugs,
     tracked as proxy bugs, not relay bugs.
   - **SSH relay (tailnet → jail sshd).** `iifname "tailscale0" tcp
     dport 2222 dnat ip to 10.99.0.2:22`, and the `forward` chain
     accepts new/established traffic only to `10.99.0.2:22`. Again
     static: no dynamic path, nothing for a client to race — the
     -79994 class has no mechanism here. Deployment constraint to
     note: the rule has no daddr match, so if this box ever enables
     Tailscale subnet routing or exit-node, transit :2222 traffic
     arriving on tailscale0 would be swallowed by the DNAT. The
     exposure is *scope*, not path: every tailnet peer can open TCP
     to the jail's sshd. Authentication is key-only, root login
     disabled, `AllowUsers muse` only (the `90-jail.conf` stanza
     written by `jail/build.sh`) — so the blast radius is exactly
     "tailnet members with a key for `muse`", and on the current
     single-owner box that is the owner. On a hosted multi-tenant
     box the tailnet itself is the tenancy boundary, and that
     boundary is the H11 multi-tenancy audit's problem — not solved
     here, stated here. The D-Bus-class analog (a guest reaching a
     host daemon that acts on the host) does not exist in this
     relay: sshd runs *inside* the jail; the host's daemons learn
     nothing from a connection that lands in the container.
   - **Planned bdrive socket bind-mount (not yet shipped)** — the
     future exception noted above, under the "No host folders, ever" bullet.
     REVIEW's round-7 owner decision specifies bind-mounting bdrive's socket into the
     jail (`[Files] Bind=`) with SO_PEERCRED acceptance of exactly
     two uids: the jail's `muse` user as seen from the host (its
     mapped uid in the `2000000` range) and, later, `obox`. For the
     day that ships, this document holds the daemon slice to six
     requirements, tracked as #169 (the socket is the one relay
     whose target involves a filesystem path, so it is the one place
     the -79994/-77179 classes could ever reach us): (1) bind the
     socket's *directory* (`/run/bdrive`), never the socket file
     alone — this is the document's own refinement of REVIEW's round-7
     owner decision ("bdrive's socket is bind-mounted into the jail"):
     a file bind mount goes stale the moment the daemon recreates the
     socket (unlink + re-bind leaves the jail holding a dead inode),
     while a directory bind always sees the current listener; (2)
     `RuntimeDirectoryPreserve=yes` on the service so a restart
     never wedges the jail's view (REVIEW finding 72); (3)
     SO_PEERCRED on every accepted connection — kernel-provided, no
     TOCTOU — matching the *exact* numeric mapped uid of the jail's
     `muse` user (2000000 + the container uid, resolved at daemon
     install from the jail's uid_map; never match the whole range,
     which would admit other host identities mapped at the same
     offset — refining the round-7 owner decision's "its mapped uid
     in the `2000000` range" parenthetical, per REVIEW finding 73),
     and `obox` later — with finding 73's limit stated plainly: this
     gate distinguishes the jail from the host, never identities
     *within* the jail. A compromised jail root can `setuid` to the
     accepted uid inside the container and SO_PEERCRED will faithfully
     report it, so the daemon must treat every accepted peer as "the
     jail" (one trust domain), never as proof of *which* jail user
     connected; (4) the daemon never
     resolves a client-supplied listen/connect path — the socket
     path comes from daemon config, never from the wire
     (`browser-driver/bdrive/config.py` already keeps it
     env-scoped, and that must survive); any other daemon-side path
     taken from the action protocol (downloads, profile dirs) must
     be resolved with dirfd pinning + `O_NOFOLLOW`; (5)
     `/run/bdrive` 0710 with group = exactly the client gid(s)
     (traverse, no list) and socket 0770, so the jail's accepted uid
     can reach the listener but enumerate nothing, while the jail's
     *other* mapped uids (jail root = host 2000000) cannot traverse
     or connect as themselves — this is a host-side boundary only:
     per finding 73 a compromised jail root can assume the accepted
     uid inside the container, so the daemon must never treat the
     accepted uid/gid as proof of which jail user connected; (6) the
     directory contains only the socket file — no
     pidfiles, logs, or other daemon state where the jail's accepted
     uid could read them — the daemon owns the directory with no
     group write, so the jail can never plant symlinks there, and
     the daemon fails closed if the directory contains unexpected
     entries.
   - **D-Bus class, stated:** no D-Bus socket is shared into the jail
     — `build.sh`'s `[Files]` section carries no `Bind=` at all, and
     systemd-nspawn forwards no host D-Bus socket into the container
     by default (`man systemd-nspawn`; a behavioral claim, not a
     vendor read). There is no guest→daemon→host path to audit. The
     one D-Bus-adjacent surface to watch is the confirmation page's
     answer→grant channel (`jail/confirm-page.md`): when it is
     implemented, the grant must be produced host-side from the
     human's browser session on confirmd — the jail must never hold
     a channel the host interprets as an approval. That is the
     standing watch item; finding 47 (the proxy hard-denies the page
     to jail traffic) is the current enforcement.
3. **Multi-tenancy is future work.** The OAuth-port-claim class —
   one sandbox attacking another's login flow — has no spark-vm analog
   today because there is one tenant per box. A hosted spark-vm with
   many tenants *will* have cross-tenant surfaces; the multi-tenancy
   audit (H11) gates the hosted design on answering them. We do not
   claim hosted trust properties for a product that isn't built yet.
4. **The guarantee is scoped to the jail architecture — which is not
   the default deployment.** The jail is committed (Owner decision 2)
   but `docs/HOSTED_GAP_ANALYSIS.md` characterizes it honestly: "spec +
   `build.sh` exist; cell isolation is a plan, not a guarantee" — it
   appears in neither `deploy/components.conf` nor ONBOARDING.md/SETUP.md.
   Everything in "What spark-vm does differently" describes that
   architecture, not what ships by default today. A plain-box self-host
   deployment (no jail) has no guest→host boundary because the agent's
   computer *is* the box — the trust boundary is between the box and
   the rest of the operator's network, and the agent runs with the box
   user's privileges. Know which shape you're running.
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
sed -n '/^\[Files\]/,/^$/p' /etc/systemd/nspawn/jail.nspawn
grep -c '^Bind' /etc/systemd/nspawn/jail.nspawn || true   # expect 0
# guest root is not host root
machinectl shell root@jail /bin/sh -c 'cat /proc/1/uid_map'  # expect 0 2000000 65536
# direct egress is dead from inside the jail
ssh -p 2222 muse@<tailnet-ip> 'curl -s --max-time 8 -o /dev/null -w "%{http_code}\n" https://example.com || echo BLOCKED'
```

## Freshness

- Vendor facts in the escape-week section were read on
  `docs.docker.com` on **2026-09-19** (Docker Sandboxes release notes,
  0.42.0, released 2026-09-07; architecture page). This document carries
  the date each vendor fact was read — treat dated facts as snapshots,
  not standing claims.
- spark-vm claims are code-verified against the cited files at this
  commit. If a cited line moves, the claim moves with it — file an
  issue if you catch drift.
