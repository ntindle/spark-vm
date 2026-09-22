# Hosted spark-vm: signup & onboarding design

**Status:** design doc for backlog item H3 (hosted-product track), written
2026-09-18. Awaiting review; implementation follows once the operator picks
the sandbox provider (Neo), the sentinel host, push infrastructure, and the
landing site location.

**Goal:** a Muse with no server of its own can discover spark-vm, sign up,
prove who it is, get a provisioned VM, and reach its box — without the
operator touching a shell per tenant.

**Scope:** discovery → signup → identity linking → provisioning → first-run.
Not covered: the provider driver itself (H4), sentinel integration internals
(H5), billing (operator decision), or the tenant-facing app beyond the signup
surface (approvals UX is H1/H2).

---

## 1. Where we are today (what this automates)

Today onboarding is manual and documented in `ONBOARDING.md` / `SETUP.md`:

1. A human provisions a plain Ubuntu 24.04 box (Unraid VM, VPS, whatever).
2. The human joins the box to *their* Tailscale tailnet (`tailscale up` +
   human-approved device auth).
3. The agent's machine joins the same tailnet.
4. On the box: create user `spark` with passwordless sudo, enable linger.
5. SSH plumbing: keypair + `ProxyCommand` for tailnet TCP, ControlMaster
   socket.
6. `git clone` the repo, run `proxy/deploy.sh`, install the secret-swapping
   egress proxy (`proxy/swap_addon.py` mitmproxy addon, running as `swapd`),
   the grant writers, the sudoers surface (`proxy/sudoers-swapd`), `confirmd`
   (approval daemon) + the approvals pages, `muse-job` (job runner), `cred-ui`
   (localhost-only credential web UI), and the CUA desktop stack.
7. The **human** installs real secrets via `cred set` or cred-ui over an SSH
   tunnel; everything the agent writes carries `hsurr:<name>` placeholders
   swapped at the proxy for allowlisted hosts only.

Every step works today. The hosted product turns steps 1–6 into an API call
and leaves step 7 exactly where it belongs: in human hands.

## 2. Actors and trust model

| Actor | Role |
|---|---|
| **Human customer** | Owns the account, pays (later), holds all real secrets. The only party that ever sees secret values. |
| **Customer's Muse** | The tenant agent. Runs its workload from its own machine and drives the tenant VM over SSH: jobs, desktop, proxy. Never sees real secrets — the `hsurr:` placeholder contract applies unchanged, scoped per tenant. (In the self-hosted reference deployment the agent is "Spark"; each hosted tenant runs their own Muse instance.) |
| **Hosted control plane** | Operator-owned. Provisions VMs, issues tenant credentials, serves the signup surface, relays tenant SSH. Sees *metadata* only (tenant id, VM id, connection metadata) — never tenant secrets. |
| **Sentinel** | Operator's abuse/safety monitor (H5). Observes tenant VMs from the outside; kill-switch path. |

**Non-negotiable invariant:** no component of the signup/provisioning path
ever handles a real secret value. Provisioning installs *software and
config*; secrets arrive later, installed by the human over an
end-to-end-encrypted channel. Any design that needs the control plane to see
a secret value is rejected.

The control plane relays tenant SSH as **TCP bytes only** — it never holds
the VM's host keys and never terminates the SSH session, so it cannot read
session content (SSH is end-to-end encrypted between the Muse/human and the
VM). What the relay *does* see is connection metadata: who connected, when,
for how long, how many bytes. That is a deliberate, stated tradeoff: the
relay is an availability chokepoint, not a confidentiality risk.

## 3. Discovery — how a Muse finds the product

Primary channels, in priority order:

1. **Muse-to-Muse word of mouth** (already live): Spark talks about spark-vm
   on musebook.lol; the repo is public at `github.com/ntindle/spark-vm`.
   Every shipped improvement is potential discovery content.
2. **README as landing page**: the repo README already carries a
   "what/why/try it" surface. The hosted signup CTA belongs at the top of
   that funnel: "No server? Get a hosted box →" deep-linking to the signup
   page. (No such CTA exists in the README today — adding it is a small
   follow-up item.)
3. **A signup landing page** (operator-hosted, URL TBD): one page, one job —
   explain the product in 30 seconds, hand the visitor (human or their Muse)
   to the signup flow. See §5 for its content.
4. **Referral**: tenant Muses get a referral token; new signups attributed to
   the referrer. (Later — not MVP.)

Discovery produces one thing: a human who wants a box for their Muse, or a
Muse whose human is bought in. Signup itself is always completed by the
human — the Muse can't sign contracts, and shouldn't hold the account.

## 4. Identity linking — proving "this Muse is that tenant's"

The hosted product must bind three things: the **account** (human), the
**tenant VM**, and the **Muse** allowed to drive it. We reuse the identity
pattern Spark already uses on musebook.lol (ed25519 keypair + signed
requests), extended with a human approval step:

1. **At signup**, the control plane creates a tenant record: `tenant_id`,
   plus an enrollment token (single-use, 15-minute TTL). The token is shown
   **once in the signup UI** (after the human's magic-link auth) for the
   human to copy to their Muse. The signup UI is the token's only channel.
2. **The Muse generates its own ed25519 keypair** locally (on its current
   machine — never transmitted). It keeps the private key; the public key
   goes to the control plane inside a *link request* carrying `tenant_id`,
   the enrollment token, the Muse's `muse_id` (its stable identity), and a
   display name for the box — the whole request **signed by the new
   keypair** (proves possession). Pasting the token to the Muse is only
   *transport*: the token is a bearer credential, and whoever submits it
   first with their own keypair would win the binding, so the token alone
   is deliberately **not** the approval.
3. **The human approves the specific key fingerprint in the signup UI.**
   The pending link request (tenant, muse_id, key fingerprint, requested
   at) appears on the signup page; the human clicks Approve. Only then does
   the control plane bind `tenant_id ↔ muse public key ↔ muse_id`. This is
   the actual countersignature: link acceptance is gated on a recorded
   human approval of *that key*, not on possession of a bearer token.
4. The private key never leaves the Muse's machine. All later
   tenant-scoped API calls (cert issuance, status polling, approval acks)
   are signed with this key.
5. **Revocation:** the human can rotate the Muse key or revoke the tenant
   from the signup dashboard. The control plane then (a) stops issuing
   certs for the old key — this gates *new* authentications only — and
   (b) sends a signed revocation signal to a privileged helper on the VM
   that terminates the tenant user's existing sessions (OpenSSH does not
   re-validate certificates on established sessions or ControlMaster
   channels, so expiry alone cannot kill them).

**Returning Muses (session 2 and beyond).** Agent platforms are ephemeral:
the keypair may die with the session. The link binds `muse_id`, so a
returning Muse presents its `muse_id` (+ previous public key if it still
has it) to request a fresh enrollment token; the human approves it with
one click in the signup dashboard (or via an email confirmation to the
human for the already-known `muse_id`). Tenant Muses *should* persist
their keypair in their platform's storage, and the protocol *must* still
work when they can't — via this re-link path. No fresh human
copy-paste is required after the first link.

## 5. Signup flow (MVP)

```
human ──▶ landing page ──▶ create account (email + magic link)
   │
   ├─▶ pick plan (paid tiers; card-required trial possible, trial terms TBD
   │       — operator decision: no free tier at launch)
   ├─▶ name the box ("nick's dev box")
   ├─▶ copy the enrollment token (shown once) to their Muse
   │       │
human's Muse ──▶ link request (signed, §4) ──▶ pending in signup UI
   │                                                    │
human ──▶ approves the key fingerprint ──▶ control plane binds tenant
   │
control plane ──▶ provision VM (H4 driver) ──▶ deploy spark-vm stack
   │
   ├─▶ issue short-lived SSH certs: one for the Muse's key (full tenant
   │    shell), one for the human (port-forward-only, no shell)
   ├─▶ hand the Muse: relay hostname + cert (the connection bundle);
   │    hand the human: one-command cred-ui tunnel script
   │
Muse polls GET /tenant/status with its key; the signup page polls the same
endpoint — when status flips to `live`, both sides see "your box is ready"
(no waiting on email).
   │
Muse ──▶ runs smoke checks (proxy swap, hello job, desktop screenshot)
   │
human ──▶ installs first secrets via cred-ui over the SSH tunnel
   │        (the one designed-manual step)
   │
Muse ──▶ first real job — the aha moment in minute ten
```

Time-to-first-box on the MVP path is **~15 minutes** (cloud-init provision;
see §7). The "first 10 minutes" clock starts at box-ready, not at signup —
the signup page says so plainly so nobody stares at a spinner.

**The landing page** (operator-hosted) needs exactly:

- 30-second pitch (what it is, who it's for: a Muse that needs a bigger
  computer).
- The two paths: "I have a server" → repo + ONBOARDING.md (today's flow);
  "I don't" → hosted signup.
- Plan/pricing summary (paid tiers; card-required trial possible, terms TBD —
  operator decision; no free tier at launch).
- The enrollment token handoff + pending-key approval UI (show once, with
  "copy for your Muse").
- Link to status/docs; nothing else. It is a funnel, not a dashboard.

**What the human does during signup (under 5 minutes of their time):**

1. Email + magic link (no password to phish).
2. Name the box, pick the plan.
3. Copy the enrollment token to their Muse; approve the key fingerprint.
4. When the page says the box is live, open the cred-ui tunnel command and
   add the first credential — the one step that stays manual by design.

## 6. Provisioning (provider-agnostic; H4 builds the driver)

The control plane talks to the sandbox provider through a narrow interface;
only the driver is provider-specific (Neo today, someone else tomorrow):

```
provision(tenant_id, spec)  -> vm_id, mgmt_endpoint
status(vm_id)               -> creating | ready | degraded | dead
dial(vm_id)                 -> bidirectional stream   # control-plane SSH +
                                                     # relay data path; the
                                                     # driver owns how this
                                                     # stream is built
ssh_info(vm_id)             -> relay_host, relay_port, vm_host_key_fingerprint
destroy(tenant_id)          -> terminal cleanup (see below)
snapshot(vm_id, label)      -> snapshot_id           # later
```

`spec` is fixed at MVP: Ubuntu 24.04, 8 vCPU / 15 GB RAM / 250 GB disk
(the reference spec from ONBOARDING.md), region pinned by the operator,
plus a network clause: `spec.network = {public_ingress: false}` — drivers
**MUST NOT** expose any public inbound path to the VM, and the control
plane verifies this post-provision. A driver that defaults to a public IP
+ open SSH satisfies nothing.

`dial()` exists so the interface never assumes the provider has a
"management network": the driver builds a stream by whatever means the
provider offers (mgmt network, serial console, or a phone-home fallback
where the fresh VM calls back to the control plane when deploy finishes).
`ssh_info()` returns the *relay* endpoint the tenant connects to plus the
VM's host-key fingerprint, which the control plane attests over the
authenticated provisioning channel — the Muse pins it in the connection
bundle (no blind TOFU).

**Provisioning sequence** (all code, no human):

1. `provision()` → VM boots from cloud-init (MVP; §7) that installs
   dependencies and clones the pinned spark-vm release.
2. Control plane opens `dial(vm_id)` and runs the deploy as the
   provisioning user: create tenant agent user (`spark`), passwordless
   sudo scoped exactly as `proxy/sudoers-swapd` defines today,
   `loginctl enable-linger`; run `proxy/deploy.sh`, the confirmd install,
   muse-job setup, cred-ui service, CUA desktop stack; write tenant config
   (`tenant_id`, control-plane callback URL, the Muse's public key, per-
   tenant swapd allowlists, audit shipping config from §10).
3. Optional: join a per-tenant Tailscale tailnet for Muses whose hosts
   support it — the control plane mints a per-tenant auth key (tagged,
   short-expiry, single-use) and injects it at first boot
   (`tailscale up --auth-key=…`). A fresh `tailscale up` cannot complete
   unattended otherwise (device approval is human-gated); the auth key is
   what makes "all code, no human" literally true. Per-tenant tailnets
   (not one tailnet + ACL tags): separate key material fails closed on
   misconfiguration, whereas a bad ACL tag rule fails open into
   cross-tenant visibility. Tailnet join is an optimization, not a
   requirement — the relay in step 5 is the primary path.
4. Health check: proxy responds, confirmd responds, muse-job accepts a
   no-op job. The check SSHes as the tenant user with a just-issued
   tenant cert (proving the cert path works end-to-end), then —
5. **Handoff: the provisioning credential is removed from the VM.**
   Post-handoff the control plane holds **no shell access** to the tenant
   VM, ever. Lifecycle from here is provider-API `destroy()` only; the
   SSH CA issues certs solely for the tenant Muse's key (full shell) and
   the human's key (port-forward-only). The tenant is marked `live`.
6. The control plane hands out the connection bundle: the Muse gets the
   relay hostname/port + its short-lived SSH cert + the pinned host-key
   fingerprint; the human gets a one-command tunnel script
   (`ssh -L 18740:localhost:18740 -N <relay>`) reaching cred-ui over SSH
   local-forward.

**Reachability model (primary).** The tenant Muse opens SSH to the control
plane's relay endpoint presenting its short-lived (≤24 h) certificate; the
relay TCP-forwards to the tenant VM over the provider path from `dial()`.
The relay never terminates SSH — end-to-end encryption holds, and the
relay cannot see session content (see §2). Explicitly ruled out: a
TLS-terminating control-plane proxy in front of cred-ui — it would let the
control plane see secret values and break the §2 invariant.

**Cert renewal.** The tenant Muse (or the tenant-side bootstrap client,
§9) renews at ~50% cert lifetime via the signed-key API; in-flight
multiplexed sessions survive expiry (renewal only gates *new*
connections). If the control plane is unreachable past expiry, new
connections fail — the control plane is a hard availability dependency
for *new* sessions (stated, not hidden); established work is unaffected.

**Destroy.** Terminal cleanup = provider volume deletion. MVP uses
per-tenant encrypted volumes; destroy = key destruction + volume
deletion, so tenant secrets (including the cred store on disk) are
cryptographically unrecoverable, not merely unlinked.

## 7. Cloud-init now, golden image later

Two ways to get the stack onto a fresh VM; MVP uses cloud-init, image later:

- **MVP — cloud-init:** the provision script installs dependencies
  (Tailscale, docker, python, node, the CUA stack), clones the pinned
  spark-vm release, and runs the deploy scripts unattended. Slower
  (~10–15 min to `ready`) but the deploy path is the *same code* as
  self-hosted, so every OSS improvement to the deploy scripts improves
  hosted provisioning for free. Debugging is transparent.
- **Later — golden image:** snapshot a known-good provisioned VM per
  release; `provision()` boots the image and runs only tenant-specific
  first-boot. Fast (~2–3 min) but adds image-build/release machinery.
  Build it when signup volume makes the 15-minute wait hurt.

First boot — whichever path — runs an explicit identity-regeneration
checklist: regenerate SSH host keys, regenerate `machine-id`, reset the
Tailscale node identity, wipe cloud-init seed/logs. Without this, tenants
share host keys (MITM confusion across tenants) and Tailscale identities
(join conflicts) — the classic golden-image footgun. The image itself
contains zero tenant data and zero secrets; first boot is what makes a VM
a tenant's.

## 8. First-run experience (the first 10 minutes after box-ready)

The signup flow ends where the product begins. The Muse's first session
should feel like unboxing, not configuring:

1. **"Your box is ready"** — the signup page and the Muse's status poll
   flip together; email is a backup, not the mechanism.
2. **Verify the box** — the Muse runs the standard smoke checks: proxy
   swaps a placeholder, muse-job runs a hello job, CUA takes a screenshot
   of the desktop.
3. **Install secrets** — the human opens cred-ui over the tunnel script
   and adds the first credential (the designed manual step; the doc says
   so plainly so nobody is surprised).
4. **First real job** — suggested starter: a long-running job via
   muse-job ("watch this repo and tell me when CI passes"), so the tenant
   feels the core value — persistent work without babysitting — in minute
   ten.
5. **Approvals** — confirmd is already running; the first approval request
   (e.g. the proxy asking to allow a new host) demonstrates the
   human-in-the-loop safety story on the approvals page.

Activation metric for the funnel: *signed up → box live → first job
completed*. That path needs zero secrets, and it measures the core value.
Track *first secret installed* separately as a trust-depth metric, not
the activation gate — gating activation on a human SSH-tunnel step would
crater the number and mislead every funnel review. The drop-off between
"box live" and "first secret installed" is still the number to watch for
onboarding friction.

## 9. Component mapping (what already exists, what needs building)

| Piece | Exists today | Hosted delta |
|---|---|---|
| Egress proxy + swapd (`proxy/`) | ✅ self-hosted | per-tenant allowlists; `tenant_id` in audit lines |
| Grant writers / sudoers (`proxy/sudoers-swapd`) | ✅ | unchanged shape; deployed per tenant by provisioning |
| `confirmd` + approvals pages (`confirm/`) | ✅ | per-tenant instance; push notifications later |
| `muse-job` | ✅ | unchanged; separate VMs isolate tenants (worktrees isolate jobs *within* a tenant) |
| `cred-ui` | ✅ localhost-only | unchanged; reached over the tenant's SSH tunnel |
| CUA desktop stack (`cua/`) | ✅ | unchanged |
| Deploy script (`proxy/deploy.sh`) | ✅ manual | wrapped by the provisioning sequence, unattended |
| Identity linking (§4) | pattern only (musebook) | **build**: link API, enrollment tokens, fingerprint approval, re-link |
| SSH relay (§6) | ❌ | **build**: TCP relay, no SSH termination |
| SSH CA + cert issuance/renewal (§6) | ❌ | **build** (standard OpenSSH CA) |
| Tenant-side bootstrap client | ❌ | **build**: one command the tenant Muse runs — keygen → link → cert → ssh-config. "Hand the Muse a config snippet and instructions" works for Spark; a bootstrap client is what makes it work for the tenth Muse with no hand-holding |
| Provisioning driver (H4) | interface sketched (§6) | **build**: Neo driver against the §6 interface + fake driver for tests |
| Landing + signup page | ❌ | **build** (operator hosts) |
| Audit log shipping (§10) | ❌ | **build** |
| Sentinel integration (H5) | ❌ | separate design |
| Billing | ❌ | operator decision |

The strategy is deliberate: **the hosted product is a thin control plane
over the existing self-hosted stack**. Every OSS improvement (proxy
hardening, muse-job fixes, confirmd polish) ships to hosted tenants
automatically because it's the same code. The per-VM (not per-process)
tenant boundary is what keeps the isolation story tractable.

## 10. Audit log shipping & outside observation

Sentinel (H5) and abuse handling both depend on operator visibility that
does *not* rely on VM shell access (which §6 removes at handoff):

- **What ships off-VM:** swapd audit lines (with `tenant_id`), confirmd
  approval decisions, and muse-job lifecycle events — as signed,
  append-only batches with per-VM sequence numbers, over a mutually
  authenticated channel (per-VM client cert issued at provision time,
  pinned to the tenant).
- **Tamper properties:** a compromised VM can *suppress* its logs but
  cannot forge them undetectably — a gap in the sequence numbers is the
  signal. Log content is integrity-protected; the operator never trusts
  a VM's claim about its own health without the sequence check.
- **Outside channels:** provider flow logs and hypervisor telemetry give
  the operator network-level observation (egress volumes, connection
  targets) independent of anything on the VM. This is what "sentinel
  watches from the outside" means concretely.
- **Kill-switch path:** the signed revocation signal from §4.5 rides the
  same mutually-authenticated channel in reverse; `destroy()` is the
  terminal backstop via the provider API.

## 11. Open questions (operator decisions)

Items marked **(NEEDS_USER.md)** are already tracked there (operator-
internal, not in this repo); the rest are design decisions for the
operator or for later loop runs.

1. **(NEEDS_USER.md) Provider**: Neo confirmed? API credentials for the
   H4 driver.
2. **Tailnet shape**: per-tenant tailnets recommended (§6.3) — operator
   confirms; who holds tailnet admin and the device-approval UX per
   tenant follows from the choice.
3. **(NEEDS_USER.md) Sentinel host + API**: where it runs, how the
   control plane and the sentinel talk (blocks H5 implementation).
4. **(NEEDS_USER.md) Push**: VAPID keypair + self-hosted vs provider
   push service (blocks H2).
5. **(NEEDS_USER.md) Landing/signup hosting + domain**: where the page
   lives.
6. **(NEEDS_USER.md) Billing**: free tier limits, paid tiers, provider —
   needed before charging, not before building.
7. **Abuse**: signup rate limits and identity-verification level for the
   free tier (email-only invites spam VMs; decide before launch, not
   after).

## 12. Phased build plan

- **Phase 0 (no operator input):** this doc; provisioning interface
  types + fake driver for tests (the fake driver is what unblocks
  interface work before the provider decision lands); SSH CA prototype;
  link-API skeleton with enrollment tokens + fingerprint approval;
  tenant-side bootstrap client.
- **Phase 1 (needs provider creds):** Neo driver; end-to-end provision of
  a real VM; golden-path deploy script hardening from the manual flow;
  SSH relay.
- **Phase 2 (needs landing host):** signup page with token handoff and
  key approval; "box is ready" status polling; first-run checklist;
  human tunnel script.
- **Phase 3:** sentinel integration (H5); push (H2); billing; golden
  image; referral.

---

*Design doc for backlog item H3 (hosted-product track), written 2026-09-18.
Status: awaiting review.*
