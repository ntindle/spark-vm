# Hosted spark-vm: signup & onboarding design

**Status:** design doc for backlog item H3 (hosted-product track), written
2026-09-18; reconciled 2026-10-22 against the shipped control-plane
surface. The "awaiting operator decisions" premise below is stale:
provider DECIDED (Fly.io), the H11 multi-tenancy audit shipped 2026-09-24
(H5 design unblocked; sentinel host still operator-held), the landing page
is live at sparkvm.dev (private waitlist since 2026-09-25), and the
box-enrollment ceremony is superseded by the shipped pairing-code protocol
(`pairing/README.md`, #844) + rotating box Bearer <redacted> (#846) + owner API
keys (#843). Sections tagged **SHIPPED** point at real code; sections
tagged **DESIGN** were never built and are still the plan.

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
3. **The signup landing page** (SHIPPED 2026-09-25: `site/` deployed at
   sparkvm.dev on Cloudflare Pages; currently in private waitlist —
   waitlist CTAs carry `?src=` attribution buckets, invite tooling in
   `site/waitlist_invites.py`). One page, one job — explain the product
   in 30 seconds, hand the visitor (human or their Muse) to the signup
   flow. See §5 for its content. The waitlist is the funnel's current
   state, not a launched signup form.
4. **Referral**: tenant Muses get a referral token; new signups attributed to
   the referrer. (Later — not MVP.)

Discovery produces one thing: a human who wants a box for their Muse, or a
Muse whose human is bought in. Signup itself is always completed by the
human — the Muse can't sign contracts, and shouldn't hold the account.

## 4. Identity linking — proving "this Muse is that tenant's"

The hosted product must bind three things: the **account** (human), the
**tenant VM**, and the **Muse** allowed to drive it. We reuse the identity
pattern Spark already uses on musebook.lol (ed25519 keypair + signed
requests), extended with a human approval step.

**Reconciled 2026-10-22:** the box-enrollment half of this section shipped
as the pairing-code protocol (#844 — see `pairing/README.md`); the
account-level binding (tenant record ↔ human account ↔ tenant Muse
identity) is still design (#1158, #1365, #1475). The shape survived the
rebuild: the human approves a *specific key fingerprint*, and a bearer
credential alone never wins the binding.

**Box enrollment (SHIPPED — #844).** The box generates its own ed25519
keypair locally (private key never leaves the box) and POSTs
`/v1/pairing/request` with `{name, pubkey}`. The plane stores the **code
hash** plus the pubkey and returns an 8-character pairing code with a
15-minute TTL. The box prints the code and the fingerprint — which the
**server computes from the pubkey itself** (the client-sent value is
ignored, so the owner always compares the true fingerprint). The owner
lists pending requests (owner API key, #843 — except the very first box,
whose approval is CLI-only; see First owner key below), compares the
fingerprint with the box screen, types the code, and approves: the plane
issues a challenge nonce, the box signs it (proof of possession), and
redeeming the signature consumes the pairing one-shot and returns the box
id plus its first 24-hour bearer. Provisioned boxes skip the human ceremony
via the attested path (provisioner-seeded single-use attestation token;
plane-side auto-approval still open (#907); wire contract #1108).

**Box credential lifecycle (SHIPPED — #846).** Box Bearer <redacted> live
24 hours. The box rotates its own token before expiry by signing a rotate
message with its ed25519 private key — a stolen bearer alone cannot
rotate the legitimate box out — with a 15-minute previous-token grace.
`POST /v1/boxes/{id}/revoke` is owner-only, immediate, idempotent. The
SSH-cert revocation mechanics in old step 5 were never built; box-revoke
+ owner-key revoke (#843) is the shipped revocation story.

**Dashboard auth surface (SHIPPED — #843/#845).** The dashboard's sign-in
is the owner API key itself (#845): the owner pastes a key, which the
dashboard keeps only in that tab's session storage — never in a cookie,
localStorage, or a URL — and clears on sign-out or tab close. The same
keys gate the fleet endpoints plane-side (#843), so the dashboard and the
API share one credential, not two. AgentID is not part of that shipped
surface: the plane-side agent-session exchange (`POST /v1/agent/exchange`,
#1225) shipped, but the dashboard AgentID sign-in half (#1199) is still
an open draft — an agent cannot yet sign in to the dashboard with
AgentID, and the owner-key paste above is the shipped path.

**First owner key (bootstrap — SHIPPED, #843).** The dashboard sign-in is
the owner-key paste — but the first owner key has to come from somewhere:
there is no setup secret and no pre-seeded key. On a fresh database, where
no owner key exists yet, the first pairing approval is CLI-only:
`spark_pair.py approve --pairing-id pair_... --bootstrap` accepts the typed
pairing code with no `Authorization` header and records the approval as
`approved_by='bootstrap'` (the pairing detail is likewise readable without
a key, so the human can still verify the fingerprint first). The box
redeems the challenge and receives its first 24-hour bearer, saved to
`enrollment.json` (0600) on the box — and that box token is the authority
for `POST /v1/owner/bootstrap`, which mints the FIRST owner key, once
(save it immediately: it is returned exactly once and the plane stores
only its hash; the full operator sequence is in
`HOSTED_AUTH_OPERATOR_RUNBOOK.md`, Day 0). After any active owner key
exists the endpoint answers `403 "bootstrap closed"`; later keys are
minted with an owner key via `POST /v1/owner/keys` (#878). There is no
account-creation step today — holding the first owner key is what makes
you the owner — and the dashboard sign-in unlocks only after that key
exists, so the very first box is always enrolled from the CLI, never from
the dashboard. (A provisioned first box is the exception: the attested
path auto-approves it, so there is no pairing to approve — see Box
enrollment above.)

Honest threat model, carried from `pairing/README.md`: on a fresh database
anyone who can reach the Worker can request a pairing and self-approve it,
so the first party to complete request → approve → redeem → owner-bootstrap
becomes the owner (first-claim race). The pairing id is 64-bit (`pair_` +
16 hex chars) and the code 40-bit (hashed): not guessable, but not a secret
either. The operator wins the race by enrolling immediately after deploy
on a trusted network; the window closes permanently at the first owner key. There is no better answer without a
setup secret (deliberately removed in #843); the alternative is an
unenrollable fresh database.

**Returning Muses (session 2 and beyond) (DESIGN).** Agent platforms are ephemeral:
the keypair may die with the session. The link binds `muse_id`, so a
returning Muse presents its `muse_id` (+ previous public key if it still
has it) to request a fresh pairing round; the human approves it with
one click in the dashboard (or via an email confirmation to the
human for the already-known `muse_id`). Tenant Muses *should* persist
their keypair in their platform's storage, and the protocol *must* still
work when they can't — via this re-link path. No fresh human
copy-paste is required after the first link. (Design pending the
account-level binding above; the pairing flow itself is re-runnable
today for boxes.)

*Key-identity companion:* the pairing flow above onboards the
*box*; the *agent's* key-pair onboarding — first-connect manifest,
"same key -> same box" resume, the claim-url bookmark rule, and the
rotate-vs-claim decision — is pinned in
[KEY_IDENTITY_ONBOARDING.md](KEY_IDENTITY_ONBOARDING.md), which also
records how key-identity accounts sit in the per-tenant-plane accounts
plan. Same key-pair primitive, different actor.

## 5. Signup flow (MVP)

```
human ──▶ landing page (sparkvm.dev, private waitlist today) ──▶ create account
   │      (DESIGN — never built; the first key is checklist step 1, below)
   │      (DESIGN: email + magic link — shipped auth surface is owner API
   │       keys (#843/#845); AgentID agent session exchange exists
   │       plane-side (#1225) but the dashboard AgentID sign-in half
   │       (#1199) is still an open draft (§4, Dashboard auth surface)
   ├─▶ pick plan (paid tiers; card-required trial possible, trial terms TBD
   │       — operator decision: no free tier at launch)
   ├─▶ name the box ("nick's dev box")
   ├─▶ box enrollment: pairing code (8 chars, 15-min TTL) + fingerprint
   │       approval — in the dashboard once an owner key exists;
   │       CLI-only (approve --bootstrap) for the very first box
   │       (SHIPPED — #844, §4, First owner key)
   │       │
box ──▶ pairing request (pubkey, §4) ──▶ pending on the plane
   │                                     (dashboard once signed in)
   │                                                    │
owner ──▶ approves the fingerprint ──▶ plane issues challenge;
   │    box redeems (proof of possession) ──▶ first 24h bearer
control plane ──▶ provision VM (H4 driver) ──▶ deploy spark-vm stack
   │
   ├─▶ first owner key: the box's first 24h bearer (#846) is the
   │    authority for POST /v1/owner/bootstrap, which mints the FIRST
   │    owner key, once (SHIPPED — #843, §4, First owner key); later
   │    keys are minted with an owner key (POST /v1/owner/keys, #878).
   │    The dashboard sign-in unlocks only after that first key exists.
   │    (the SSH-cert issuance in the 2026-09-18 design is DESIGN, not built)
   ├─▶ hand the box: relay hostname/port + pinned host-key fingerprint
   │    (the connection bundle); hand the human: one-command cred-ui
   │    tunnel script
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

**The landing page** (SHIPPED: sparkvm.dev on Cloudflare Pages, private waitlist) needs exactly:

- 30-second pitch (what it is, who it's for: a Muse that needs a bigger
  computer).
- The two paths: "I have a server" → repo + ONBOARDING.md (today's flow);
  "I don't" → hosted signup.
- Plan/pricing summary (paid tiers; card-required trial possible, terms TBD —
  operator decision; no free tier at launch).
- The pairing-code handoff + fingerprint approval UI (SHIPPED: 8-char code,
  15-min TTL, shown with the server-computed fingerprint for the owner to
  compare with the box screen — #844).
- Link to status/docs; nothing else. It is a funnel, not a dashboard.

**What the human does during signup (under 5 minutes of their time):**

1. (SHIPPED — #843) Get the first owner key: enroll the first box from
   the CLI — on the box run `spark_pair.py redeem` (it waits for the
   approval), then `spark_pair.py approve --pairing-id pair_... --bootstrap`;
   the redeem completes and saves its first bearer to `enrollment.json`
   (0600); `POST /v1/owner/bootstrap` with that bearer mints the first
   owner key, once (save it immediately — returned exactly once; see
   `HOSTED_AUTH_OPERATOR_RUNBOOK.md`, Day 0). That key is the dashboard
   sign-in (§4, First owner key). (DESIGN) The email + magic-link account creation in the 2026-09-18 design was never built — there is no
   account-creation step today; holding the first key is what makes you
   the owner. AgentID agent session exchange exists plane-side (#1225)
   but the dashboard AgentID sign-in half (#1199) is still an open draft
   (§4, Dashboard auth surface).
2. Pick the plan (the box was named when its pairing was requested in step 1).
3. (SHIPPED — #844) Approve the pairing code's fingerprint in the dashboard (for later boxes; the first box's approval is the CLI step in 1 above). The 2026-09-18 enrollment-token copy step is superseded — the pairing code is shown on the box screen.
4. When the page says the box is live, open the cred-ui tunnel command and
   add the first credential — the one step that stays manual by design.

## 6. Provisioning (provider-agnostic; H4 builds the driver)

The control plane talks to the sandbox provider through a narrow interface;
only the driver is provider-specific (Fly.io, DECIDED 2026-09-18; H4 may run against the live API within the $5/run + $25/month caps, DECIDED 2026-09-24):

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

**Provisioning sequence** (all code, no human on the primary relay path;
optional BYO-tailnet step 3 is human-gated):

1. `provision()` → VM boots from cloud-init (MVP; §7) that installs
   dependencies and clones the pinned spark-vm release.
2. Control plane opens `dial(vm_id)` and runs the deploy as the
   provisioning user: create tenant agent user (`spark`), passwordless
   sudo scoped exactly as `proxy/sudoers-swapd` defines today,
   `loginctl enable-linger`; run `proxy/deploy.sh`, the confirmd install,
   muse-job setup, cred-ui service, CUA desktop stack; write tenant config
   (`tenant_id`, control-plane callback URL, the Muse's public key, per-
   tenant swapd allowlists, audit shipping config from §10).
3. Optional: join the box to the tenant's own tailnet (BYO Tailscale).
   The tenant box joins the *human's* tailnet — the account holder's own
   Tailscale network — never a control-plane-minted per-tenant tailnet,
   and the control plane mints no Tailscale auth keys. Enrolling the box
   needs a human step by Tailscale's design: the device appears in the
   human's tailnet admin as pending and the human approves it there, so
   the "all code, no human" claim does not apply to this path — the
   relay in step 5 is the primary path and stays fully unattended.
   Network posture: the box lives on the tenant's own tailnet — never a
   shared tenant-to-tenant network — so a misconfigured tailnet rule
   cannot expose one tenant to another, and the control plane holds no
   cross-tenant key material to misconfigure. Tenant isolation on the
   relay path is the H11 multi-tenancy audit's call. (Decided
   2026-09-19 hosted unblock pass, P11: BYO Tailscale supersedes the
   earlier per-tenant-tailnet recommendation. The exact enrollment
   handshake — join intent at provision time vs the human running
   `tailscale up` post-handoff — is the identity-service turn's call,
   H9.)
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

**Cert renewal (DESIGN — the SSH-CA model was never built; shipped auth is 24h box bearer <redacted> rotated by the box itself, #846).** The tenant Muse (or the tenant-side bootstrap client,
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
| Identity linking (§4) | ✅ box enrollment (pairing-code protocol, `pairing/`, #844) + box token rotation (#846) + owner API keys (#843) + dashboard owner-key sign-in (#845) | **build**: account-level binding — tenant record (#1158), first-manifest-write actor (#1365), per-signup VAPID issuance (#1475). First owner key: minted from the first box's bearer via `POST /v1/owner/bootstrap` (one-shot; §4, First owner key); later keys via `POST /v1/owner/keys` (#878) |
| SSH relay (§6) | partial (relay probing/wiring machinery in `hosted/`) | **build**: tenant-facing TCP relay, no SSH termination |
| SSH CA + cert issuance/renewal (§6) | ❌ (superseded) | **design only**: shipped auth is owner API keys (#843) + 24h box Bearer <redacted> (#846); no OpenSSH CA built |
| Tenant-side bootstrap client | ✅ shape shipped (`pairing/spark_pair.py`: keygen → pairing → token storage, #844) | extend: ssh-config emission + `live` status polling |
| Provisioning driver (H4) | interface sketched (§6); provider DECIDED Fly.io; live-API caps DECIDED ($5/run, $25/mo) | **build**: Fly driver against the §6 interface + fake driver for tests; upstream-asset preflight shipped (#1878) |
| Landing + signup page | ✅ `site/` live at sparkvm.dev (private waitlist since 2026-09-25) | signup form proper + pairing-code handoff UI |
| Audit log shipping (§10) | ❌ | **build** |
| Sentinel integration (H5) | H11 audit shipped 2026-09-24 (design unblocked) | **build** the H5 design; sentinel host still operator-held |
| Billing | DECIDED: no free tier at launch; card-required trial possible | provider TBD; trial terms TBD |

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

1. **(NEEDS_USER.md) Provider**: RESOLVED 2026-09-18 — Fly.io (Machines API;
   `custom.flyio` API token connected and verified). Loop-provisioned
   machines may run against the live API within $5/run + $25/month caps
   (DECIDED 2026-09-24, auto-destroy at slot end).
2. **Tailnet shape**: DECIDED (2026-09-19 hosted unblock pass, P11):
   BYO Tailscale — the tenant box joins the account holder's own
   tailnet; the control plane mints no auth keys and no per-tenant
   tailnets. The earlier per-tenant-tailnet recommendation (§6.3,
   pre-decision) is superseded. Device-approval UX lives in the human's
   own tailnet admin, not the signup UI; the identity-service turn (H9)
   owns the exact enrollment handshake.
3. **(NEEDS_USER.md) Sentinel host + API**: where it runs, how the
   control plane and the sentinel talk. No longer blocks H5's *design*
   (H11 audit shipped 2026-09-24 — design is loop work; host still
   operator-held).
4. **(NEEDS_USER.md) Push**: VAPID keypair operator-generated at setup
   (blocks H2 implementation).
5. **(NEEDS_USER.md) Landing/signup hosting + domain**: RESOLVED
   2026-09-25 — sparkvm.dev on Cloudflare Pages (project
   `sparkvm-dev`), private waitlist. Signup form proper still to build
   (§9).
6. **(NEEDS_USER.md) Billing**: DECIDED 2026-09-18 — no free tier at
   launch; card-required trial possible (trial terms TBD). Provider still
   TBD — needed before charging, not before building.
7. **Abuse**: signup rate limits and identity-verification level at
   launch (email-only invites spam VMs; decide before launch, not
   after). The card-on-file trial is the mining-abuse control — the
   "free tier" framing in the 2026-09-18 version is superseded by the
   no-free-tier decision.

## 12. Phased build plan

- **Phase 0 (no operator input):** this doc; provisioning interface
  types + fake driver for tests; SSH CA prototype (DESIGN, superseded by
  the bearer/box-token model); link-API skeleton with enrollment tokens
  + fingerprint approval (SHIPPED as the pairing-code protocol, #844);
  tenant-side bootstrap client (SHIPPED shape: `pairing/spark_pair.py`).
- **Phase 1 (needs provider creds — resolved: Fly.io, $5/run +
  $25/month caps):** Fly driver; end-to-end provision of a real VM;
  golden-path deploy script hardening from the manual flow; SSH relay.
- **Phase 2 (needs landing host — resolved: sparkvm.dev live, private
  waitlist):** signup page with pairing-code handoff and fingerprint
  approval; "box is ready" status polling; first-run checklist;
  human tunnel script.
- **Phase 3:** sentinel integration (H5); push (H2); billing; golden
  image; referral.

---

*Design doc for backlog item H3 (hosted-product track), written 2026-09-18.
Reconciled 2026-10-22 against the shipped control-plane surface: box enrollment
(#844), box token lifecycle (#846), and owner API keys (#843) are shipped; the
account-level binding is still design (#1158, #1365, #1475).*
