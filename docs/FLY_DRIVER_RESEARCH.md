# Fly.io driver research (H4)

Date: 2026-09-20. Strategy loop, research archetype, hosted-product track.

## Why

H4 (the Fly provisioning driver) was unblocked by the hosted unblock pass
(BACKLOG.md): Fly.io chosen, the `custom.flyio` token connected and verified.
The provider-agnostic interface every driver implements is sketched in
`docs/HOSTED_SIGNUP_ONBOARDING.md` §6 (PR #24): `provision` / `status` /
`dial` / `ssh_info` / `destroy` (+ `snapshot` later), `spec.network =
{public_ingress: false}`, plus the planned H4 contract extensions named in
the backlog: `suspended`/`waking` states, async `dial()` wake, an open
`gpu_class` shape descriptor (not a closed enum), a suspend-vs-park
distinction, and `destroy` that deletes volumes. This pass grounds each of
those against the real Fly.io Machines API (base `https://api.machines.dev`,
reference `https://docs.machines.dev/`) before the feature run builds the
driver. Read-only API verification performed 2026-09-20 against the
org-scoped `custom.flyio` token (GraphQL `organizations` query: one org,
`personal` / "Nicholas Tindle" — token works; see F6).

## Headline finding

**The §6 "MVP — cloud-init" provisioning path does not map to Fly as
written** (no cloud-init on the platform, Fly's own init is PID 1, the
rootfs is ephemeral — F1). The §6 "Later — golden image" path maps
cleanly, and it is the recommended production path. But it is **not** the
only viable path: a stock-image + exec-install-to-`/data` architecture is
evaluated in F1b and kept as a parallelizable alternative, so R2's
image-build work is a strong recommendation, not a hard H4 gate. The true
shared prerequisite for either path is the non-systemd supervision design
(open item 2).

## Findings

### F1 — no systemd, no cloud-init, ephemeral rootfs: golden image is the recommended path

- Fly runs its own `init` as PID 1 on every machine; it cannot be replaced
  ("We run our own `init` as PID 1. It can't be replaced by anything else
  as it's responsible for doing some initialization during machine boot
  and providing API for things like `fly machine exec`." — Fly staff,
  community.fly.io/t/14416). The documented workaround (systemd in its own
  PID namespace via `unshare --pid --fork --mount-proc`) is a hack the same
  staff do not recommend for `systemctl`-dependent tooling.
- spark-vm's stack is systemd-based: `proxy/deploy.sh` installs units, and
  `cred-ui`/`confirmd` ship as systemd services (e.g. `cred-ui.service`).
  The §6 provision sequence step 2 — create the `spark` user,
  `loginctl enable-linger`, run `proxy/deploy.sh`, install confirmd /
  muse-job / cred-ui / the CUA desktop stack — **cannot run as-written on
  Fly**.
- Fly's root filesystem is ephemeral: "If your app writes files, installs
  packages, or modifies anything at runtime, those changes vanish when the
  machine stops. On the next boot, it's back to the clean image."
  (superfly/docs, current HEAD, verified 2026-09-20). GPU-enabled machines
  are documented at a 50 GB rootfs limit; CPU machines are likewise
  size-bounded. There is no persistent rootfs to install onto at provision
  time, and no cloud-init mechanism exists on the platform.
- **Consequence for H4:** the driver must boot a golden OCI image with the
  whole spark-vm stack baked in (services supervised without systemd —
  see open item 2), and treat the 250 GB Fly Volume as the only persistent
  disk. This vindicates the ten-minute spec's golden-image direction for
  the Fly deployment. Whether the image pipeline is a *hard* H4
  prerequisite or a later optimization depends on the alternative
  evaluated in F1b.

### F1b — alternative evaluated: stock image + exec-install into `/data`

The "only path" reading above is too strong. There is a second viable
architecture, and the doc's own F3 already assumes its key mechanism:

- **Shape:** boot a stock Ubuntu OCI image (`ubuntu:24.04` runs on Fly),
  attach the 250 GB volume at machine create, and **exec-install the
  deploy scripts into `/data` at provision time** via the Machines exec
  API — the structural twin of the §6 MVP cloud-init path, preserving §7's
  "every OSS improvement to the deploy scripts improves hosted
  provisioning for free." Services are supervised from `/data` by a
  non-systemd supervisor (s6, supervisord, or tini) launched from the image
  entrypoint under Fly's init — no systemd anywhere.
- **Structural advantage over the golden image:** it avoids the §7
  golden-image identity footgun entirely. A fresh stock image means fresh
  host keys and machine-id by construction; the host-identity regen
  checklist §7 requires for baked images is unnecessary.
- **Hard questions, honestly:**
  - *exec API timeouts:* a full stack install is ~10–15 minutes; exec
    calls have timeouts. Workaround is background-and-poll (`nohup` the
    install, poll completion via further exec calls) or splitting the
    install into idempotent steps. This must be validated at build time —
    the channel is assumed, not proven.
  - *first-boot volume formatting:* the volume arrives unformatted and the
    mount/format sequencing must be validated (options: confirm Fly
    tolerates attaching an unformatted volume and format via exec, or a
    throwaway formatter step). Open validation item for the feature run.
  - *interrupted install:* provision is already async; make the install
    steps idempotent and retry via re-exec, with destroy + re-provision as
    the terminal fallback.
- **Costs of the alternative:** 10–15 minute provision latency (a paid
  signup UX problem vs seconds for a golden image), per-provision apt
  egress, and weaker reproducibility than a pinned image artifact.
- **Sequencing conclusion:** golden image remains the *recommended*
  production path, but H4 can proceed **in parallel** with R2 via the
  exec-install path. Both paths share the true prerequisite: the
  non-systemd supervision design (open item 2). "R2 blocks H4" is
  downgraded to "R2 is the recommended path; the exec-install alternative
  is documented and unblocked."

### F2 — suspend AND park both map: Fly offers both primitives

- `POST /v1/apps/{app}/machines/{id}/suspend` starts suspension; states
  `suspending` → `suspended`; resume is `POST .../start`, which attempts a
  snapshot resume and falls back to a cold start if the snapshot was
  discarded. Suspend works in all Fly.io regions (since July 2024).
  Suspended machines bill storage-only — no CPU/RAM charges.
  (fly.io/docs/reference/suspend-resume/, current superfly/docs HEAD,
  verified 2026-09-20.)
- **Suspend-vs-park, mapped per the decided definition**
  (`docs/GPU_PATH_RESEARCH.md`: "`suspend`" = full-state suspend-to-disk,
  H13's meaning; "`park`" = terminate the compute, keep the data volume,
  reprovision + reattach + re-run bootstrap on wake):
  - `suspend` → **suspend**: memory + rootfs snapshot kept, storage-only
    billing. The driver's idle primitive.
  - `stop` → **park**: compute terminated, the 250 GB data volume kept,
    rootfs reverts to the golden image on next start — i.e. reprovision
    (boot the golden image) + reattach (the volume) + re-run bootstrap
    (the first-boot identity checklist). (Under the F1b exec-install path,
    a park-reset instead boots the stock image and re-runs the entrypoint
    bootstrap from `/data`.) This is exactly the park pattern
    the H4 contract was designed around (RunPod's "suspend" is likewise
    park). The earlier draft's "destructive-to-OS-state" framing was
    wrong under the golden-image path: the image *is* the OS state, so
    nothing provisioned is lost.
- Resume caveat, disclosed: if the suspend snapshot is discarded, resume
  falls back to a cold start — a wake silently becomes a park-like reset
  (rootfs back to image). The driver must surface which resume path was
  taken so the control plane can distinguish wake from park-reset.
- Contract mapping for the feature run:
  - `status()` `suspended` ↔ Fly machine state `suspended`
  - `status()` `parked` ↔ Fly machine state `stopped` (surfaced distinctly
    from `suspended`, per the status table)
  - `status()` `waking` ↔ Fly machine state `starting` reached via a
    resume-`start` (as opposed to a cold boot)
  - async `dial()` wake = `POST .../start` then
    `GET .../wait?state=started` (use the `/wait` endpoint, not a poll loop)
- **Recommendation (not a mandate):** prefer `suspend` as the idle
  primitive pending H13's idle economics — suspend keeps wake fast, park
  trades wake latency for zero compute cost. The interface draft carries
  both words; the operator policy chooses.

### F3 — interface mapping table (H3 §6 → Machines API)

| H3 interface op | Fly.io mapping |
|---|---|
| `provision(tenant_id, spec)` | 1. Create the `tenant-<id>` app (GraphQL `createApp` or the `fly apps create` equivalent) — the Machines API requires the app to exist before volumes/machines can be created under it. 2. Create the 250 GB volume (`POST /v1/apps/{app}/volumes`, ≤ 500 GB max — spec fits). 3. `POST /v1/apps/{app}/machines` with `guest: {cpu_kind: "performance", cpus: 8, memory_mb: 16384}` (the `performance-8x` preset = 8 CPU / 16 GB — covers the 8 vCPU / 15 GB reference spec), `region` pinned by the operator, `image` = the pinned golden-image ref (see F3b), `mounts: [{volume: "vol-<tenant>", path: "/data"}]`, and **no `services` block** (see F4). Machine creation is async: wait on `GET .../wait?state=started`. |
| `status(vm_id)` | `GET /v1/apps/{app}/machines/{id}`: `created`/`creating` → `creating`; `started` → `ready`; `suspended` → `suspended`; `stopped` → `parked` (surfaced distinctly from `suspended` — see F2); `starting` (via resume) → `waking`; `stopping` → transitional; `destroying`/`destroyed` → `dead`. |
| `dial(vm_id)` | Two paths, matching §6's "the driver owns how this stream is built": (a) **provisioning phase** — the Machines exec API (`POST .../machines/{id}/exec`) for non-interactive deploy steps, served by Fly's init; (b) **post-handoff relay data path** — the control plane holds a WireGuard peer on the org 6PN private network (`fly wireguard create`) and TCP-forwards to `<machine-id>.vm.<app>.internal`. (The peer lives on the org-wide 6PN and therefore crosses per-tenant app boundaries; this is acceptable because the relay forwards only to the specific machine's 6pn address and never terminates SSH.) The §6 phone-home fallback also works: machine egress is open by default. The relay still never terminates SSH — end-to-end encryption holds per the §6 reachability model. |
| `ssh_info(vm_id)` | Unchanged from §6: the *relay* endpoint (`relay_host`, `relay_port`) the tenant connects to, plus the VM host-key fingerprint attested over the authenticated provisioning channel. Fly contributes the 6pn address as the relay's upstream, not the tenant-facing value. |
| `destroy(tenant_id)` | `DELETE /v1/apps/{app}/machines/{id}` + `DELETE /v1/apps/{app}/volumes/{vol}` (+ `DELETE` the app if one-app-per-tenant, F6). |
| `snapshot(vm_id, label)` (later) | Fly volume snapshots exist (create-from-snapshot supported); machine memory snapshots are Fly-internal. Deferred to the later slice per §6. |

### F3b — the image registry/push path (the `image` value made actionable)

F3's provision mapping is not implementable without this: "`image` = the
golden spark-vm OCI image" is not a value the Machines API accepts.

- **Publish path:** the golden image is pushed to Fly's registry,
  `registry.fly.io`, by the image-build pipeline (R2 feature half) — not
  by the driver. Machine-config `image` ref format:
  `registry.fly.io/<app>/<image>:<tag>`, digest-pinned
  (`registry.fly.io/<app>/<image>@sha256:<digest>`) for reproducibility.
- **Ownership:** the image pipeline builds, pushes, and pins the ref; the
  driver takes the pinned ref as operator-set config and references it at
  machine create. Registry auth is token-derived (`fly auth docker` flow) —
  the pipeline holds the push credential, the driver's provision path only
  needs the pull-side ref.
- **Feature-run validation:** confirm the exact digest-pin behavior of the
  Machines API `image` field against `https://docs.machines.dev/` at build
  time (tag vs digest acceptance, registry auth scoping for the per-app
  deploy token in F6b).

### F4 — `public_ingress: false` is expressible and verifiable

- A machine created with no `services` in its config gets **no public
  ingress**; the Fly edge only routes to machines that declare services.
  The driver must additionally ensure the app holds no allocated IPs
  (a driver that defaults to `fly ips allocate-*` + open SSH satisfies
  nothing, per §6).
- Post-provision verification (the control plane "verifies this
  post-provision", §6): `GET` the machine and assert `services` is empty,
  plus a GraphQL `ipAddresses(appName: ...)` query asserting zero
  allocations. Both are read-only checks the driver can run after every
  provision.

### F5 — `gpu_class`: the Fly driver must refuse GPU shapes fail-closed

- Fly's own GPU docs (current superfly/docs HEAD, fetched 2026-09-20)
  carry the banner: **"GPUs are deprecated and will be unavailable after
  August 1."** This corroborates `docs/GPU_PATH_RESEARCH.md`'s
  July-31-2026 removal finding (superfly/docs#2449) — the deprecation
  stands and has taken effect.
- Consequence for the open `gpu_class` descriptor: it needs a
  **provider-routing rule**, not just a shape description. A non-empty
  `gpu_class` must route to the GPU provider driver (RunPod is the current
  recommendation, per the C6 decision — still contingent on the two checks
  named in `docs/GPU_PATH_RESEARCH.md`: the `public_ingress: false` clause
  check and the Secure Cloud availability load test) and the Fly driver
  must **reject GPU-shaped specs fail-closed** at `provision()` time. The
  Fly driver's shape table is CPU-only by construction.

### F6 — token scoping shapes the tenancy model: one app per tenant

- Verified 2026-09-20: the `custom.flyio` token answers the org-scoped
  GraphQL `organizations` query. Fly Machine tokens cannot be scoped
  narrower than app-wide (third-party operator runbook, consistent with
  Fly's token model). Therefore **one Fly app per tenant**
  (`tenant-<id>`) is the isolation shape: the per-app deploy token's
  (F6b) blast radius is then bounded to that tenant's app, and a
  compromised tenant machine can never hold the token (it only ever sees
  the exec/phone-home channel, never the API credential).
- This answers part of H11's "who holds root / trust boundary" questions
  for the Fly deployment: per-tenant apps are the unit of isolation, and
  `destroy(tenant_id)` deleting the app is the terminal cleanup.
- **Correction to the earlier blast-radius reasoning:** one-app-per-tenant
  bounds nothing *under the org-scoped token verified above* — that token
  can exec into every tenant's machines. The isolation benefit depends on
  the per-app token design in F6b, not on one-app-per-tenant alone.

### F6b — handoff on Fly: the exec tension and the token design

§6 invariant 5 (HOSTED_SIGNUP_ONBOARDING.md:247): "Handoff: the
provisioning credential is removed from the VM. Post-handoff the control
plane holds **no shell access** to the tenant VM, ever." On Fly this
invariant has a gap the interface draft must close explicitly:

- **The tension:** the Machines exec API is not a VM-side credential that
  can be removed at handoff — it is a standing platform capability held by
  whoever holds the Fly API token, for the machine's lifetime. F6's
  "a compromised tenant machine can never hold the token" points the wrong
  way: the threat invariant 5 guards against is the *control plane*
  retaining shell into the *tenant's* box, which a standing exec-capable
  token gives it permanently.
- **The mechanism Fly supports** (verified against current superfly/docs
  `flyctl/integrating.html.md`, 2026-09-20): per-app deploy tokens
  (`fly tokens create deploy -a <app> -x <expiry>` — "can only deploy and
  manage the specified app") and per-command machine-exec tokens
  (`fly tokens create machine-exec -a <app> --command "<cmd>" -x 1h`).
  Recommended lifecycle:
  1. At provision, the control plane uses the org token to create
     `tenant-<id>` and immediately mints a per-app deploy token for it.
  2. Provisioning steps run under short-lived machine-exec tokens (one
     command each) or the per-app token — never the org token.
  3. At handoff, the control plane **discards any org-token path to the
     tenant app** and retains only the per-app deploy token.
  4. Post-handoff operations under the per-app token: `suspended` /
     `waking` via `POST .../suspend` / `POST .../start` (H13 wake-on-dial),
     `status()` reads, and terminal `destroy()` (machine + volume + app).
- **Residual tension, stated plainly:** a per-app deploy token still
  grants exec into the tenant's machine, so "no shell access post-handoff,
  ever" is not literally satisfiable while H13's wake-on-dial needs a
  surviving token. The feature run must either (a) verify against
  `https://docs.machines.dev/` whether machine-level exec can be disabled
  at handoff while start/stop/destroy still work, or (b) bring an
  operator-signed revision of §6 invariant 5 (e.g. "no shell access except
  through the tenant's own authenticated relay path; the surviving
  control-plane token is app-scoped, expiry-bounded, and every use is
  audit-logged"). This is an open decision, not a settled design — but the
  feature run cannot build the driver without answering it.

### F7 — spec fit: 8 vCPU / 15 GB / 250 GB

- `performance-8x` = 8 CPU cores / 16 GB RAM (per `fly platform vm-sizes`,
  documented in community.fly.io/t/12559) — covers the reference spec's
  8 vCPU / 15 GB with headroom.
- 250 GB volume ≤ 500 GB Fly volume maximum (documented on the GPU
  getting-started page, current HEAD).
- Volumes are region-locked to their machine; the operator pins one region
  (e.g. `dfw`) per the §6 spec — capacity for `performance-8x` in the
  pinned region should be re-verified at driver build time.
- Volumes are encrypted at rest by the platform (LUKS block-device
  encryption; fly.io security page, current HEAD, verified 2026-09-20).
  Honest difference from §6's "per-tenant encrypted volumes; destroy =
  key destruction": on Fly the keys are platform-managed, so `destroy`'s
  terminal guarantee is **volume deletion**, not per-tenant key
  destruction. Tenant-data isolation between tenants is by separate
  volumes/apps, not separate keys.

## Proposed interface-level contract language (for the H4 interface draft)

H4's first slice drafts the *provider-agnostic* interface, which must also
serve the RunPod GPU driver (F5's routing rule sends all GPU shapes there)
and a future Neo driver. The findings above mix two layers; this section
splits them so the interface draft doesn't inherit Fly-only guarantees:

- **`suspended` (interface):** "the cheapest idle state that preserves all
  tenant data on the persistent volume and supports wake via `dial()`
  within the documented wake budget; the driver MUST document exactly what
  is and isn't preserved (memory? rootfs delta? network connections?)."
  *Fly instantiation:* memory + rootfs snapshot kept; resume documented as
  potentially breaking existing network connections (clients reconnect).
  *Known divergence:* RunPod's stop preserves the volume but not RAM — a
  RunPod driver would document RAM-not-preserved under the same interface
  word. The interface word is the cost/wake promise, not the snapshot
  mechanism.
- **`waking` (interface):** transitional state entered when `dial()`
  initiates a wake; the driver documents its expected latency budget.
  *Fly instantiation:* machine state `starting` reached via resume-`start`.
  *Caveat carried from F2:* a resume that falls back to cold start is
  surfaced as a park-like reset, not a wake.
- **`parked` (interface):** "compute terminated, tenant data preserved on
  the persistent volume, wake = reprovision + reattach + re-run bootstrap"
  (the decided definition from `docs/GPU_PATH_RESEARCH.md`). *Fly
  instantiation:* machine state `stopped` (see F2); resume-from-park is a
  fresh boot of the golden image with the volume reattached.
- **`gpu_class` (interface):** open shape descriptor, not a closed enum.
  **Proposed §6 amendment** (for the interface draft to adopt or reject —
  not settled here): add a provider-routing rule alongside "only the driver
  is provider-specific." The control plane routes a non-empty `gpu_class`
  to a GPU-capable driver; any driver that cannot satisfy the requested
  shape rejects `provision()` fail-closed. *Fly instantiation:* the Fly
  driver rejects all GPU shapes (F5).
- **`destroy()` terminal guarantee (interface):** parameterized per
  provider rather than inheriting §6's "cryptographically unrecoverable"
  wording. *Fly instantiation:* volume deletion (platform-managed LUKS
  keys — F7's honest difference).
- **`degraded` (interface):** no Fly machine state maps to this; it is
  control-plane-derived from health checks, not a platform state. Noted so
  the feature run doesn't go hunting for a Fly `degraded`.

## What this changes in the backlog

- H4's first slice ("provider-agnostic interface draft ... is the first
  slice") can proceed, using the interface-level contract language above —
  not the Fly instantiations verbatim.
- R2's golden-image work is the recommended production path for H4, not a
  hard gate: F1b documents the exec-install alternative that lets H4
  proceed in parallel. The true shared prerequisite is the non-systemd
  supervision design (open item 2).
- The H4 contract extensions get their Fly answers: `suspended`/`waking`
  and async `dial()` wake are native (`/suspend` + `/wait`); `gpu_class`
  needs the provider-routing rule (F5, framed as a proposed §6 amendment);
  suspend-vs-park mapped (F2): `suspend` = H13 suspend, `stop` = park;
  `destroy`-deletes-volumes is native (F3).
- The handoff invariant needs an explicit answer before the driver is
  built: per-app token lifecycle is specified (F6b), but the residual
  exec-vs-"no shell ever" tension is an open operator decision.

## Open items for the feature run

1. Supervision redesign (true shared prerequisite): inventory every
   systemd unit `deploy.sh` installs and define the non-systemd
   supervision (s6/tini/supervisord) for both the golden-image and the
   F1b exec-install paths.
2. Golden-image build pipeline (R2 feature half) — recommended production
   path; or validate the F1b alternative's open questions (exec timeout
   behavior for a ~10–15 min install, first-boot volume format sequencing,
   interrupted-install recovery).
3. Volume-mount contract: what lives on `/data` vs baked into the image
   (tenant home? swapd state? confirmd pending? audit-shipping buffer?).
   Provision-time writes (e.g. the R2 injector's placeholder swaps, and
   the F1b exec-install path's entire stack) must target `/data`, never
   the ephemeral rootfs — the rootfs resets to the image on every stop.
4. Confirm the exec API's user context for provision steps against
   `https://docs.machines.dev/` at build time.
5. Post-provision `public_ingress: false` verification queries (F4) +
   measured suspend-resume latency for the async-`dial()` wake budget.
6. One-app-per-tenant is the recommended tenancy shape (F6) — H11's audit
   validates or corrects it. Per-app token minting at provision is the
   mechanism that makes the shape meaningful (F6b).
7. Re-verify `performance-8x` capacity in the operator-pinned region and
   current pricing against the cost floor in `docs/PRICING_THINKING.md`.
8. Resolve the handoff invariant: verify whether machine-level exec can be
   disabled at handoff (docs.machines.dev), or bring the operator-signed
   §6 invariant-5 revision (F6b).
