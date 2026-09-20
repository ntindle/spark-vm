# Multi-tenant isolation research

Date: 2026-09-19 (strategy-loop run started 2026-09-19 20:54 CDT; web survey
conducted 2026-09-20 ~01:55–02:10 UTC, cited below as "surveyed 2026-09-20").

## Why

`docs/HOSTED_GAP_ANALYSIS.md` §11 names multi-tenancy "the biggest structural
gap" and files **H11**: a multi-tenancy audit that inventories every
localhost-only / no-auth / single-owner assumption, ranks by blast radius,
and must explicitly answer four design questions:

1. **Isolation story** — per-tenant box vs per-tenant processes vs
   per-tenant tailnets. Recommend one explicitly.
2. **Swap-proxy trust boundary** — swapd holds real secrets on the same box
   that runs tenant agent code. What is the assumed boundary?
3. **Fail-open vs fail-closed** — for tailnet-gated auth.
4. **Who holds root** — on a tenant box.

This pass is the **research half**: the vendor and open-source precedent H11
needs to answer those questions with evidence instead of taste. H11 (the audit
itself) decides; nothing here is a decision. The already-decided context this
research must not re-litigate: BYO Tailscale (hosted unblock pass, 2026-09-19),
the jail as the agent's runtime cell (owner decision 2), and the
both-supported default (every finding is read for hosted *and* self-hosted).

Prior art in the corpus: the competitor pass's isolation axis scorecard
(`docs/COMPETITOR_ANALYSIS.md`, per-VM tier); the org-policy research
(`docs/ORG_POLICY_RESEARCH.md`, PR #101 — mechanism tables with an honest
spark-vm column, the pattern this doc follows); the secrets-posture research
(`docs/SECRETS_POSTURE_RESEARCH.md`, PR #81).

## Honest spark-vm column (code-verified at `f64d735` — the branch base; the
original write-up was verified at `e6d1a13` and every claim re-verified
unchanged after rebasing onto the merged #91 secrets-dir enforcement,
which only hardens the facts below)

What the repo actually implements today — the substrate H11 inherits:

- **The jail** (`jail/README.md`, `jail/build.sh`): the agent's SSH login
  lands in a persistent **systemd-nspawn container**, not on the host. Guest
  root is uid-mapped (`PrivateUsers=2000000:65536` — container uid 0 is host
  uid 2000000; the README documents why `PrivateUsers=yes` was rejected).
  nftables `table inet jail`'s jail-egress rules DNAT only the proxy ports (10.99.0.1:18080/
  18081) and jail→everything-else is dropped; the agent user `muse` has
  **passwordless sudo inside the jail**; there are **no host mounts**, no
  host secrets/state/logs inside, no DNS. swapd, bdrive, the audit log, and
  the confirmation page live on the **host**. `/home/swapd/secrets` and
  `/home/swapd/inference-secrets` are additionally enforced
  `swapd:swapd` 0700 at every deploy plus a load-time warning on drift
  (merged as #91 — closes the gap open issue #91 documented; the
  operator-with-sudo fact below stands regardless).
- **confirmd** (`confirm/confirmd.service`): runs as user `swapd`, binds the
  tailnet address only, authenticates every request by Tailscale identity
  against `CONFIRM_OWNER`; partial systemd sandboxing (`PrivateTmp=yes`,
  `ProtectSystem=full`); `NoNewPrivileges` is deliberately NOT set (it calls
  `sudo -n tailscale whois/status`).
- **cred-ui** (`cred-ui/cred-ui.service`): localhost-only, **no systemd
  sandboxing at all** (open issue #115), and no authentication beyond a
  non-secret header (open issue #86).
- **The shared-root-domain fact:** the operator-with-sudo domain (on the
  current box: the `ntindle` account; the hosted signup design provisions a
  `spark` operator account — either way, a human with passwordless sudo)
  holds passwordless sudo on the same host where swapd holds real secrets. The
  jail separates the *agent* from the secrets; nothing separates the
  *operator* from anything. For one tenant (the owner) this is coherent.
  For N tenants it is not a multi-tenant substrate: there is **no tenant
  dimension in auth, secrets, approvals, or audit** today.

So the repo already contains a per-tenant-*process* shape (one jail) and a
per-tenant-*box* shape (the whole box). H11's job is to pick which one scales
to N tenants — or to say the jail generalizes. The precedent below is what it
gets to cite.

## Vendor survey (surveyed 2026-09-20)

Tenant-boundary claims are vendor-quoted with URLs; the other columns
paraphrase vendor docs. Page dates given where shown,
otherwise "no date shown". `[INFERRED]` marks synthesis; `[THIRD-PARTY]`
marks non-vendor claims.

| Vendor | Tenant boundary (vendor-quoted) | Secret broker placement | Egress default | Notes |
|---|---|---|---|---|
| E2B | "an **isolated Linux VM**" ([docs](https://e2b.dev/docs/sandbox), no date shown) | Egress proxy with `transform.headers` injected on matching requests ([docs](https://e2b.dev/docs/sandbox/internet-access), no date shown; verified live 2026-09-20 — the old `e2b-dev/docs` GitHub blob deep-link has gone 404 after E2B's docs migration, same content now served here) | Deny-capable: rules keyed by host, host must be referenced via `allowOut` | Public URL per sandbox (contrast with H3's `public_ingress: false`) |
| Daytona | "**isolates each sandbox using container and/or microVM technology**, ensuring that one Customer's runtime environment cannot interact with another's" ([security exhibit](https://www.daytona.io/docs/en/security-exhibit/), no date shown) | — | Configurable allow-lists + network-level firewall | Deliberately hedges container vs microVM |
| Modal | "**Sandboxes are built on top of gVisor**… the blast radius of any malicious code will be limited to the **Sandbox container itself**" ([docs](https://modal.com/docs/guide/sandbox-networking), no date shown) | — | **Fail-open**: "By default, Sandboxes can make outbound connections to any public IP address" (closable) | The outlier: container, not hardware VM |
| Vercel Sandbox | "**Each sandbox runs in a secure Firecracker microVM** with its own filesystem and network" ([docs](https://vercel.com/docs/sandbox), no date shown) | "**Credentials brokering injects secrets into outbound requests without exposing them inside the sandbox**… never enter the sandbox" ([sandbox page](https://vercel.com/sandbox)) | Modes: allow-all / deny-all / user-defined | Broker **outside** the guest |
| Runloop | "**Isolated, ephemeral virtual machines**… created on demand, and deleted when they are no longer needed" ([docs](https://docs.runloop.ai/docs/devboxes/overview), no date shown) | "Connect agents to LLM APIs via Agent Gateways… **without exposing your real credentials to the devbox**" (same docs) | Network Policies, deny-capable | Broker **outside** the guest |
| AgentComputer | "**isolated Firecracker instances directly on bare metal hosts**" ([site](https://www.agentcomputer.ai/), fetched 2026-09-20) | — | Port policy **unverified** on vendor pages fetched (third-party-reported public-by-default with a `--private` opt-out — needs a vendor citation before H11 relies on it) | Bare-metal hypervisor |
| TermSquad | None stated (no date shown) | **Inside the box**: "Configure your own API key inside your TermSquad Computer" ([features](https://termsquad.com/features/any-agent)) | Undocumented | The counterexample: keys live with the agent |
| Cloudflare | "**Each sandbox runs in a separate VM**, providing complete isolation… **For complete isolation, use separate sandboxes per user**" ([docs](https://developers.cloudflare.com/sandbox/concepts/security/), lastUpdated 2025-11-08) | — | Outbound works; inbound needs explicit exposure | Warns co-tenancy inside one sandbox is the wrong model |
| Fly.io / Sprites | "**Use microVMs when: You're building a multi-tenant system where one tenant's workload must not be able to affect another's**" ([learn](https://fly.io/learn/microvm-vs-container/), no date shown) | — | Sprites: "**Each sandbox gets its own private network by default**… Isolation is the default" | Per-tenant box + private-by-default network |
| WSO2 Agent Manager | None stated (announcement dated 2026-09-15) | — | — | Only per-agent *identity/governance* separation claimed; physical boundary unverified |

**Pattern, [INFERRED]:** the dominant vendor answer for mutually-untrusted
tenants is **one hardware-isolated box/microVM per tenant** (E2B, Vercel,
Runloop, AgentComputer, Cloudflare, Fly). Container-tier tenancy exists —
Daytona deliberately hedges container vs microVM, Modal uses gVisor — and is
always paired with a stronger mechanism than plain processes. Nothing surveyed
puts mutually-untrusted tenants on plain processes with no additional
boundary. On the secret broker, the serious products (Vercel, Runloop, E2B's
egress proxy) all place the broker **outside the guest**; TermSquad is the one
that keeps keys inside the box — and that is exactly the shape H11 must not
bless.

**Root posture:** no vendor in this survey publishes exact root-user semantics
([INFERRED] across all ten). The consistent posture is high privilege *inside*
the guest (Vercel documents "system-privileged processes"; [THIRD-PARTY]
Daytona's VM class runs as root) with the host/hypervisor vendor-only. Nobody
withholds root inside the tenant's unit *and* shares the host.

## OSS mechanism menu (surveyed 2026-09-20)

For the compute boundary options H11 weighs, plus defense-in-depth for the
shared-host shape:

- **systemd sandboxing** (`PrivateTmp`, `ProtectSystem`, `ProtectHome`,
  `PrivateUsers`, `RestrictAddressFamilies`, `NoNewPrivileges`,
  `SystemCallFilter`, … — `systemd.exec(5)`): **defense-in-depth for host
  services on the shared-host shape** — hardens confirmd/swapd-class
  services; it is **not the tenant boundary** and complements either compute
  shape. Two caveats straight from the man page: (1) **graceful degradation
  is fail-open** — "many of these sandboxing features are gracefully turned
  off on systems where the underlying security mechanism is not available";
  any tenant sandbox built on these must assert effective confinement at
  startup (`systemd-analyze security` exists) and refuse tenants if it is
  unavailable. (2) Read-only-path options **do not lock down AF_UNIX
  sockets** — co-tenants can still reach each other's IPC unless socket
  paths are walled off separately. Directives harden a *service*; they do
  not create a *tenant boundary*.
- **Namespaces** (user + network + mount): necessary substrate, not a
  boundary — "Namespaces in Linux are simply mechanisms to partition kernel
  resources… they do not enforce true security separation." One shared
  kernel: one kernel CVE takes all tenants. For agents that run arbitrary
  shell, install packages, and fetch URLs, namespaces alone are polite
  separation.
- **gVisor / Kata / Firecracker** (stronger-than-container options):
  gVisor = per-sandbox userspace kernel, OCI-native, **no KVM required**,
  roughly ~50–100 ms added start and ~10–30% I/O-path tax (rough community
  benchmarks, not vendor-published), syscall-compat gaps;
  Kata = per-workload guest kernel (hardware boundary), needs KVM,
  roughly ~125–500 ms boot depending on backend (rough benchmarks); Firecracker = minimal microVM, ~125 ms boot,
  snapshot/restore in ms, needs KVM. **Operational note for the strategy
  loop:** the hosted product is *assumed* to run on virtualized cloud hosts
  (unverified assumption — see the nested-KVM open verification below); without
  verified nested KVM, **gVisor is the only one of the three that works**.
  Firecracker/Kata imply bare-metal or nested-virt-capable hosts (verify
  before choosing).
- **bubblewrap / nsjail**: per-*process* sandboxes (namespaces + seccomp +
  cgroups), no daemon. Production users: Compiler Explorer runs production
  compiler/user-binary execution in nsjail; Google kCTF; Windmill wraps job
  execution in nsjail; Anthropic reportedly uses bubblewrap for Claude CLI
  sandboxing on Linux [THIRD-PARTY]. Scope note: these sandbox **individual
  tool calls inside a tenant**, not tenants from each other — right tool for
  sandboxing an agent's code execution, wrong layer for the tenant boundary.
- **Tailscale for the network layer**: the multi-tenant pattern is **one
  tailnet + per-tenant tags + default-deny ACLs** (tag bound at
  operator-controlled key enrollment via `tagOwners`; never by the tenant
  device). The tailnet default policy is allow-all until restrictive ACLs are
  authored — isolation exists only if the operator writes the deny-by-default
  policy, and "ACL file missing/unapplied" must mean deny (fail closed).
  Tailscale gives *network* isolation ("who can reach whom"), not *host*
  isolation. Note the already-decided BYO shape: tenants bring their own
  tailnets, so per-tenant tailnets exist by construction on the tenant side;
  the ACL/tag machinery above is for the **operator's** reachability plane.

## The IMDS warning (swap-proxy trust boundary)

The closest real-world precedent for a secret-holding proxy co-located with
tenant workloads is the cloud **metadata service** (169.254.169.254) — and it
is a cautionary tale. IMDSv1's trust model was "the request came from this
instance, therefore it is authorized": any process on the box — including an
attacker's SSRF payload inside a tenant's app — could mint cloud credentials.
The industry's fix (IMDSv2) had three parts: per-request session tokens the
tenant can't forge, tokens bound to the requesting interface, and hop-limit 1
so tokens can't be forwarded off the requesting interface.

Applied to spark-vm [INFERRED — no public precedent was found for a
secret-swapping egress proxy sharing a box with tenant agents; this is the
novel part of the design]:

1. A proxy that swaps `hsurr:` placeholders for real secrets, keyed only on
   "the request came from this box", is **IMDSv1**. Copy IMDSv2's fixes:
   per-request authentication the tenant cannot forge (not source IP — every
   local process shares it), swaps bound to the requesting **tenant
   identity** (the proxy must know *which tenant* asks and only swap *that
   tenant's* secrets), and token scoping so credentials can't leave the
   requesting interface (IMDSv2's hop-limit-1: it doesn't stop guests from
   reaching the endpoint, it stops the token from being forwarded off the
   requesting interface — a container or guest behind NAT can't steal the
   host's credentials).
2. **Fail closed on proxy failure**: if swapd is unreachable, requests must
   fail — never pass through with placeholders intact (a placeholder
   reaching an upstream un-swapped), never substitute via a fallback path. The secure
   default is "no credentials issued", not degraded mode.
3. Audit every swap (already the design; cloud-trail logging of credential
   issuance is the precedent).
4. Endgame: workload identity with short-lived tokens (Azure managed
   identity / GCP service accounts / IAM Roles Anywhere pattern) — the
   platform attests *which workload* calls and issues short-lived tokens,
   instead of a proxy holding long-lived secrets at all. The swap proxy is
   the transitional mechanism, not the destination.

The jail already moves spark-vm one step in this direction: the agent's
workloads run in the container while swapd holds secrets on the host. H11
must decide whether that container boundary — shared kernel, operator-owned
host — is a sufficient tenant boundary, or a v0.

## Three-shape comparison (for H11)

| Shape | Compute boundary | Network | Who holds root | Cost / complexity | Honest fit |
|---|---|---|---|---|---|
| **Per-tenant box** | Hypervisor (full VM per tenant) | Per-tenant private network (Fly Sprites pattern); BYO tailnet per tenant | Tenant root inside guest; operator holds hypervisor | Highest infra cost; simplest trust story | Vendor consensus; matches the signup doc's provision-per-tenant model (H4) |
| **Per-tenant processes** (jail-per-tenant on shared host) | nspawn container + uid map + nftables (the jail, generalized to N) | Shared host network + per-tenant tags/ACLs, or BYO tailnet per jail | Operator holds host root; tenant gets contained guest-root-equivalent | Cheapest; shared kernel = weaker boundary | The in-repo v0. Honest only if documented as weaker than hardware isolation — fine for cooperative tenants, not for adversarial ones |
| **Per-tenant tailnets** | — (network layer only) | Separate key material per tenant; fails closed on cross-tenant visibility | (orthogonal — the network layer doesn't change who holds root on the compute) | Complements either compute shape | Already decided (BYO). Answers "who can reach whom", never "who can read whose files" |

Note on the "per-tenant processes" label: it means **the jail specifically**
(nspawn container + uid map + nftables, generalized to N tenants) — not plain
processes, not systemd-hardened services, and not gVisor. gVisor is a
distinct, stronger-than-container option that would sit *inside* the
per-tenant-processes row as an upgrade to the container runtime, not as a
separate shape.

**Research-shaped findings for H11 to adopt or reject** (operator/H11 decides):

1. **Compute:** per-tenant box is the vendor consensus for mutually-untrusted
   tenants. The jail generalizes to per-tenant processes honestly *only* if
   the weaker shared-kernel boundary is documented as such — it is a cost
   optimization, not a security equivalence. Do not sell nspawn as a
   hardware boundary.
2. **Proxy:** outside the tenant guest (Vercel/Runloop precedent), with
   IMDSv2-style per-tenant request auth, tenant-scoped secrets, fail-closed
   on failure, every swap audited. A co-located proxy that cannot
   authenticate *tenants* is IMDSv1 — known-bad.
3. **Tailnet:** BYO stands. Operator reachability rides its own tailnet with
   per-tenant tags + default-deny ACLs, tag binding at operator-controlled
   enrollment, missing policy = deny. For tailnet-gated auth the semantics
   split: (a) **enrollment-time / new-request auth** fails closed — an
   auth-lookup failure denies (enrollment is control-plane dependent; the
   local `tailscale whois`-style identity lookup is a different failure
   domain with the same fail-closed prescription); (b) **existing
   sessions through a control-plane outage** survive on the data plane
   without the coordinator, so revocation cannot propagate during an outage
   — fail-open for revocation semantics. (b) is **unverified** (see Open
   verifications); H11 must verify it before relying on Tailscale for
   lockout semantics, and must never assume an outage "degrades into
   bypassed identity checks" — the failure mode to design for is
   *stale authorization*, not bypass.
4. **Root:** tenant (human owner) may hold root inside their unit; the
   operator exclusively holds the layer below. The current shared
   `ntindle`-with-sudo domain matches no vendor precedent — H11 must name
   which layer the operator exclusively owns, and must not let the human's
   and the agent's privilege domains collapse into one (if both hold guest
   root, treat the guest as compromised by design and keep secrets
   out-of-guest per finding 2).
5. **In-guest tooling:** nsjail/bubblewrap are the right layer for sandboxing
   an agent's *individual code executions* inside its tenant boundary — not
   for the tenant boundary itself. Don't confuse the two.

## Claimable vs forbidden (honesty rules for H11's output)

- **Claimable:** "per-VM tenant boundary, same tier as E2B/Vercel/Cloudflare"
  (only for the per-tenant-box shape); "credential broker outside the
  (agent) guest" — **true today for the jail**: swapd holds secrets on the
  host, the guest carries placeholders only (code-verified,
  `jail/README.md`). The *per-tenant* extension of finding 2 (per-tenant
  request auth, tenant-scoped swaps) is NOT implemented and may not be
  claimed until it is; "jail: no host mounts, uid-mapped, proxy-only egress"
  (code-verified, `jail/README.md`).
- **Forbidden:** "container isolation equivalent to a VM" (shared kernel);
  "per-tenant tailnets isolate tenants" (network only); "systemd sandboxing
  contains tenants" (service hardening, fail-open degradation, no IPC
  lockdown); "secret broker isolated from the operator" — today the operator
  shares swapd's host (the `ntindle`-with-sudo domain), so broker/operator
  separation is a finding-2 follow-up, not a current property; any root
  claim about vendors (undocumented — see survey caveats).

## Open verifications (later turns; nothing blocked)

- Nested KVM availability on the hosted product's target hosts (decides
  whether Firecracker/Kata are even options; gVisor works regardless).
- Tailscale control-plane-outage semantics for existing sessions
  (fail-closed for enrollment is architectural; existing-session behavior
  needs verification before H11 relies on it).
- Vendor root semantics remain publicly undocumented for all ten vendors —
  do not assert them; re-survey if any vendor publishes an isolation
  whitepaper.
- WSO2 Agent Manager's physical tenant boundary (unverified); TermSquad's
  isolation primitive and egress policy (unstated).

## Sources

Vendor (fetched or search-verified 2026-09-20): E2B docs (sandbox,
internet-access, public-url); Daytona security exhibit; Modal sandbox
networking guide; Vercel sandbox docs + sandbox page; Runloop devboxes
overview; AgentComputer site + docs + computer-guest repo; TermSquad features
pages; Cloudflare Sandbox SDK security + architecture + containers concepts;
Fly.io Learn microVM-vs-container; WSO2 Agent Manager GA announcement
(2026-09-15). OSS: `systemd.exec(5)`; gVisor docs; Kata Containers;
Firecracker benchmarks (micro-containers, rl-training-sandboxes);
nsjail/bubblewrap (google/nsjail, containers/bubblewrap, Google
code-sandboxing catalog, Compiler Explorer nsjail docs); Tailscale ACL/tag
patterns (community deployment docs + SKILL references); Fly.io private
networking docs; IMDS analyses (Azure managed-identity docs, IMDSv2
hop-limit/token-binding writeups). Full URLs are inline above.

## Follow-ups (for H11 / later turns)

- H11 audit: adopt/reject the five research-shaped findings; answer the four
  design questions with citations to this doc.
- The jail-per-tenant generalization needs a design spike (per-tenant
  secret stores, tenant-identity-bound swaps, per-jail nftables) before it
  is more than a paragraph — candidate for a build-loop `arch`/`feature`
  turn once H11 rules.
- Quarterly re-survey trigger: any vendor isolation-whitepaper publication,
  or a sandbox-escape week recurrence (cf. `docs/COMPETITOR_ANALYSIS.md`
  C13, the Docker escape-week item), re-opens the vendor table.
- If hosted v1 targets virtualized hosts, spike gVisor as the
  stronger-than-nspawn process boundary (no nested KVM needed).
