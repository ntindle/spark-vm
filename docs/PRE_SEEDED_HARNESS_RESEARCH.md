# Pre-seeded harness research (R2)

**Status:** research + pre-seed contract, implementation in slices. **Slice 1
SHIPPED 2026-09-19** (`harness/`): `harness-auth-probe` (the R1 §5 probe —
gate/provision modes, Bearer wire-shape assertion, placeholder-never-leaks
assertion), `generate-image-manifest.sh` + `check-image-manifest.sh`
(golden-image manifest + the injector's fail-closed preflight), 21 hermetic
tests. **Slice 2 SHIPPED 2026-09-20** (`harness/`): `install-gate-fixture.sh`
+ `echo-fixture.py` — the gate fixture installer (public non-secret dummy
credential under the inference proxy's fixed `llm-api` name through the
narrow writers, `bearer_header` placement, loopback echo host bound +
allowlisted for swapping and exempted in the inference proxy's own
`inference-ssrf.allow`, fail-closed against overwriting a real
credential — the guard requires the registry to show `llm-api` bound
only to the echo host AND a blind compare
(`proxy/cred-store-verify-inference`, which never reveals the stored
value) to confirm the stored value is the public dummy — with the
gate-fixture cleanup contract, 20 hermetic installer
tests. Remaining for later feature slices: provision-time injector
(which owns the gate-fixture teardown — unbind the llm-api→echo-host
binding and remove the echo host from inference-hosts.allow and
inference-ssrf.allow — before the real key lands), image gate, R1
script green.
The remaining implementation (provision-time injector, image gate) is
build-loop `feature` work; this doc remains the spec input for it.
**Feeds:** `docs/FIRST_TEN_MINUTES_SPEC.md` §5 (the harness pre-seed contract
is R2's interface — this doc fills it in; the spec is unmerged, PR #49 @
`3788907` — this contract is pinned to that revision, re-check the section
numbers if the spec moves). **Follow-ups:** H4 (provisioning
driver runs the injector), H9 (tenant identity), H10 (per-tenant approvals),
H12 (metering the tenant's inference spend), H15 (tenant secret onboarding).

## 1. The question

The adoption research (Finding 2) says pre-seeded state beats onboarding
docs: the tenant Muse's first ten minutes must contain **no first-run picker,
login prompt, or interactive setup**. The R1 spec §5 fixes the *interface* —
`</dev/null timeout 10 <harness-auth-probe>` must exit 0 with stdin closed —
and leaves R2 to define the probe per harness, the image/injection split, and
the top-3 snag list. This doc does that for spark-vm's harness.

The harness = the agent runtime surface the tenant Muse drives: `muse-job`
(spawns `muse --yolo`), the inference proxy (`:18081`, swaps in the model
credential), the credential-swapping proxy + `cred` store, `confirmd`
approvals, the CUA desktop stack, and SSH/tailnet reachability.

## 2. What the market already does

The task-scoped sandbox market has converged on one split: **bake the
toolchain at build time, inject tenant state at create time.**

- **E2B templates** (`e2b template build --dockerfile …`): versioned images
  with deps + desktop pre-installed (reported ~6x cold-start improvement);
  tenant state goes in at create time, e.g.
  `Sandbox.create(template=…, { envs: { ANTHROPIC_API_KEY: "…" } })`.
  Build-time secrets use BuildKit `--mount=type=secret` so they never land
  in image layers.
- **PuppyOne's scope-sandbox** (custom E2B template) is the cleanest exemplar:
  hardened sshd + websocat BAKED so cold connect skips the per-create
  install; connect-time only *seeds the user's key and starts the
  pre-installed daemons*. Template builds are treated as deliberate, billable
  deploy steps, with the runtime spec kept in sync with the Dockerfile.

Nothing here is novel — the point is that spark-vm's pre-seed design should
follow the industry split rather than invent one.

## 3. Inventory: first-run interactive state per component

Inventory from the repo (main @ 8aa7d0d); the Muse-CLI auth-flow detail is
operator-box knowledge (the live spark-vm's Muse Code login), not
repo-verified — noted in the row:

| Component | First-run interactive state today | Pre-seed class |
|---|---|---|
| `muse-job` → `muse --yolo` | Muse CLI auth must exist before a job spawns (operator box today: `~/.config/muse/auth.json` via device-code login — operator-box knowledge, not in the repo) or a provider key is swapped in. **Unvalidated:** no repo evidence the Muse CLI supports static-key auth or base-URL/proxy routing (see §6.2) | IMAGE: CLI + plugin installed/approved; INJECT: tenant inference credential |
| Inference proxy `:18081` | `llm-api` stored human-only via a fixed registry path (SETUP.md "Inference-model recipe") | IMAGE: proxy unit + registry path + gate fixture (dummy credential + echo host, public); INJECT: the key itself (operator, provision time, by-name reference) |
| `cred` / swapd | cred-ui localhost-only (ONBOARDING.md §4); `cred set` human-only in the human's own SSH session (ONBOARDING.md §5) | IMAGE: swapd daemon + grant writers + bundle-build step; FIRST-BOOT: fresh swapd CA generated per tenant, cert installed into the trust bundle (never bake the CA private key — mitmdump generates it at `/home/swapd/.mitmproxy/`) |
| `confirmd` | the approvals URL must reach the human (the summons, R1 §4) | IMAGE: confirmd; INJECT: per-tenant approvals URL (H10) |
| CUA desktop | `./cua/bin/cua-desktop.sh start` (Xvfb :98, XFCE, cua-driver, bridge :18731) | IMAGE: everything, autostarted at boot |
| SSH / tailnet | key-only SSH, tailnet join, the VM user | IMAGE: users, sshd config, CA trust; INJECT: tenant keys/identity (H9) |
| muse-job plugin | `muse plugins install --force` + `approve` | IMAGE: installed + approved in the image |

The proxy's swap model already *is* this split: the swapd daemon,
allowlists, and grant writers are deploy-time; credential VALUES are
human-installed at runtime and never baked. R2 generalizes the existing
pattern to the whole harness.

## 4. The split rule

> **Bake everything non-secret, non-tenant, and versioned. Inject everything
> per-tenant or secret-bearing. Never bake a secret — public, non-secret
> fixtures excepted. Never inject a toolchain** (once the golden image
> exists; R2 accelerates H3's "Later" phase — H3's MVP cloud-init path
> still installs the toolchain at provision until the image replaces it).

Bake placeholders, not secrets: the load-bearing detail that makes the
invariant workable is the proxy's existing `hsurr:<name>` pattern — the
image bakes `hsurr:llm-api` in the muse inference config, and the proxy
swaps in the real value at egress. Placeholders are safe to bake; values
never are.

- **Golden image** (built deliberately, versioned, checksummed): OS, the
  agent user, sshd config, both swap proxies + units, the swapd CA
  *bundle-build step* (the CA itself is generated per tenant at first boot —
  mitmdump's private key must never be in the image), grant writers, `muse`
  CLI + `muse-job` plugin installed *and approved*, the CUA desktop stack,
  `confirmd`, the cred-ui service, the empty credential stores with their
  fixed registry paths, the gate fixture (dummy inference credential +
  echo host in `inference-hosts.allow`, public and non-secret — §5.4), and
  the public `smoke-test` credential dummy R1 §3a requires. Because plugin
  install/approval, the muse config, and the CUA autostart are user-scope
  (and the repo has no CUA autostart unit), the image bakes a skeleton home
  (`/etc/skel`) plus a first-boot unit that instantiates the per-agent-user
  services on first login — nothing user-scoped is assumed to already exist
  in a live home directory.
- **Provision-time injection** (runs once per tenant at `provision`, before
  box-live): tenant identity (keys/certs per H9); the tenant's inference
  credential — installed by the *operator* through the existing human-only
  grant-writer path (SETUP.md "Inference-model recipe"), referenced by the
  injector by name only; the injector asserts presence and probes, and never
  handles, logs, or persists the value (this keeps H3's "all code, no human"
  provisioning and the human-only secret path compatible: the value travels
  the human channel, the provisioner only verifies the registry entry); the
  fresh swapd CA + trust-bundle install; tenant attribution wired into
  confirmd (H10); the first-task slot properties. Injection rides H3's
  authenticated control-plane provision sequence (the H4 driver implements
  the interface).
- **Image versioning.** The image version is the repo SHA the manifest was
  built from, recorded in the manifest alongside the registry paths and
  unit names the injector expects. The pin lives in the H4 provision spec
  (an `image_version` field — a spec extension the feature run proposes);
  the control plane also holds a "current golden" pointer for the default.
  Rollback = repoint the pointer (or pin the older version) and
  reprovision. The injector preflights: it asserts the image's manifest
  version matches its own expectations and fails closed before box-live
  on any drift.
- **Never at either stage:** a real credential in an image layer, a
  device-code OAuth login inside the first-run window, or a prompt that
  waits on stdin.

## 5. The auth probe (R1 §5's `<harness-auth-probe>`, concretely)

For spark-vm's harness the probe is a non-interactive end-to-end check that
the tenant Muse's runtime can think and act. The feature run implements it;
it must satisfy exactly:

1. `</dev/null timeout 10 <harness-auth-probe>` — stdin closed, 10 s cap.
2. Exit 0, zero prompts. Any prompt, hang, or timeout = the box fails the
   harness check: report and stop, same handling as a failed smoke check.
   The probe must never improvise credentials or walk anyone through a login.
3. What it verifies, in order: (a) the runtime a spawned turn drives is
   authenticated — a headless `muse-job` spawn's model calls must route
   through the inference proxy and the proxy must swap in a valid
   credential (proves the injected `llm-api` equivalent is present and
   working — this is the auth that matters); (b) `confirmd` answers
   (proves the approvals path the first task needs is up). A cheap
   token-burn probe (a single minimal completion through the same proxy
   path) is acceptable evidence for (a) inside the 10 s budget — it need
   not be a full `muse --yolo` spawn, as long as it exercises the
   identical auth path. Probe runs on every image build and every
   provision burn inference spend: keep them minimal and count them under
   the tenant's metered usage (H12), never the operator's silent overhead.
4. The golden-image gate (R1 §6.7) runs the probe on every image build and
   refuses to publish the image if it fails — the PuppyOne rule: keep the
   runtime install path working with injection disabled, so a broken image
   is caught at build time, not at a tenant's box-live. Gate mode works
   because the image carries the gate fixture (§4): the gate installs the
   public dummy inference credential and points the probe at the echo host,
   so probe check (a) exercises the full swap path against a fixture; the
   real tenant key replaces the fixture at provision. Fixture lifecycle:
   the echo-host binding, its `inference-hosts.allow` entry, and its
   `inference-ssrf.allow` exemption must be torn down when the fixture is
   replaced — by the image-build gate before publish, or by the
   provision-time injector before it installs the real key — so no box
   holding a real credential can ever swap it toward the echo server (see
   `harness/README.md` "Fixture lifecycle"). A gate
   failure means the image is broken; a provision-time probe failure means
   the injected credential is wrong — the two are distinguishable by
   design.

## 6. Top-3 snags (what still needs a human after R2)

1. **Whose inference credential funds the tenant Muse.** The probe verifies
   *a* credential is installed and working; it cannot decide the funding
   model. Operator-funded `llm-api` + per-tenant metering (H12) vs
   bring-your-own-key at signup is the remaining Billing-provider decision —
   the no-free-tier / card-required-trial / per-box substance is already
   decided (NEEDS_USER.md), the provider choice and its consequence are not.
   R2's implementation works around this with the operator's current
   default; it does not resolve it.
2. **Muse CLI auth must be proxy-key-based, never OAuth — and that is the
   highest-risk unvalidated assumption in this doc.** The operator's
   device-code login (`~/.config/muse/auth.json`) does not transfer to
   tenants and must never be baked into the image. The tenant path is the
   inference proxy's swapped credential; the refresh/re-auth path is an
   operator runbook, never a tenant-interactive flow. But: there is zero
   repo evidence the Muse CLI supports static-key auth or custom
   base-URL/proxy routing — `muse-job` only ever spawns `muse --yolo`, and
   SETUP.md's inference recipe describes only the proxy side. The feature
   run must validate this *first*: if the CLI is OAuth-only, the harness
   needs a different runtime or a different auth path, and the probe
   contract (§5) collapses. Do not build the image before this is proven.
3. **Tenant identity injection: tailnet shape is decided, H9's mechanics are
   not.** NEEDS_USER.md records BYO Tailscale (the tenant links their own
   tailnet at signup), so the injector's identity step is cert/SSH-key
   issuance per H9 — not tailnet ACLs. What stays open: H9's fingerprint
   verification and re-link rate limits, and the H15 tenant
   secret-onboarding funnel that gates the cred-injection half. R2 ships the
   image half and the injector *interface* now; the H9 mechanics fill the
   identity step when H9 lands.

## 7. Handoff to the feature run

The build-loop `feature` implementation of R2 should deliver, in order:
(1) the golden-image manifest (what bakes, versioned, checksummed);
(2) the provision-time injector implementing §4's inject list against the
H4 `provision` interface; (3) `<harness-auth-probe>` per §5;
(4) the golden-image gate refusing broken images; (5) the R1 first-run
script run green against the result. Injector failure semantics: if
provision-time injection fails, box-live must not flip — it maps to R1's
`provisioning-failed` taxonomy ("Box setup failed — we're retrying"), never
to a silently degraded box. Snags 1–3 above stay tracked in
NEEDS_USER.md / H9 / H12 / H15 — the feature run does not resolve them,
it works around them with the operator's current defaults.

## Limitations

This is research and contract, not implementation: nothing here has run
against a live provisioner (the Neo provider is undecided — H4), the
multi-tenant pieces it injects into (H9/H10/H11) don't exist yet, the
probe's exact command is deliberately left to the feature run, and the
Muse-CLI static-key-auth capability (§6.2) is asserted as a requirement,
not demonstrated — it is the highest-risk open validation. The external
precedent (E2B templates, PuppyOne's build/connect split) is market practice
for task-scoped sandboxes, not a controlled experiment on Muse-as-customer —
the R7 pilot remains the validation path for the transfer.
