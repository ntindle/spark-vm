# Pre-seeded harness research (R2)

**Status:** research + pre-seed contract. The implementation (golden-image
build, provision-time injector, auth probe) is a build-loop `feature` item;
this doc is its research half and its spec input.
**Feeds:** `docs/FIRST_TEN_MINUTES_SPEC.md` §5 (the harness pre-seed contract
is R2's interface — this doc fills it in). **Follow-ups:** H4 (provisioning
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
| `muse-job` → `muse --yolo` | Muse CLI auth must exist before a job spawns (operator box today: `~/.config/muse/auth.json` via device-code login — operator-box knowledge, not in the repo) or a provider key is swapped in | IMAGE: CLI + plugin installed/approved; INJECT: tenant inference credential |
| Inference proxy `:18081` | `llm-api` stored human-only via a fixed registry path (SETUP.md "Inference-model recipe") | IMAGE: proxy unit + registry path; INJECT: the key itself (operator, provision time) |
| `cred` / swapd | cred-ui localhost-only (ONBOARDING.md §4); `cred set` human-only in the human's own SSH session (ONBOARDING.md §5) | IMAGE: swapd + CA + grant writers + trust store; INJECT: tenant creds via the signup funnel (H15) |
| `confirmd` | the approvals URL must reach the human (the summons, R1 §3) | IMAGE: confirmd; INJECT: per-tenant approvals URL (H10) |
| CUA desktop | `./cua/cua-desktop.sh start` (Xvfb :98, XFCE, cua-driver, bridge :18731) | IMAGE: everything, autostarted at boot |
| SSH / tailnet | key-only SSH, tailnet join, the VM user | IMAGE: users, sshd config, CA trust; INJECT: tenant keys/identity (H9) |
| muse-job plugin | `muse plugins install --force` + `approve` | IMAGE: installed + approved in the image |

The proxy's swap model already *is* this split: the swapd daemon,
allowlists, and grant writers are deploy-time; credential VALUES are
human-installed at runtime and never baked. R2 generalizes the existing
pattern to the whole harness.

## 4. The split rule

> **Bake everything non-secret, non-tenant, and versioned. Inject everything
> per-tenant or secret-bearing. Never bake a secret; never inject a toolchain.**

- **Golden image** (built deliberately, versioned, checksummed): OS, the
  agent user, sshd config, both swap proxies + units, swapd CA baked into the
  system trust store, grant writers, `muse` CLI + `muse-job` plugin
  installed *and approved*, the CUA desktop stack autostarting at boot,
  `confirmd`, the cred-ui service, and the empty credential stores with
  their fixed registry paths.
- **Provision-time injection** (runs once per tenant at `provision`, before
  box-live): tenant identity (keys/certs per H9), the tenant's inference
  credential installed through the inference registry path, tenant
  attribution wired into confirmd (H10), and the first-task slot properties.
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
   is caught at build time, not at a tenant's box-live.

## 6. Top-3 snags (what still needs a human after R2)

1. **Whose inference credential funds the tenant Muse.** The probe verifies
   *a* credential is installed and working; it cannot decide the funding
   model. Operator-funded `llm-api` + per-tenant metering (H12) vs
   bring-your-own-key at signup is the remaining Billing-provider decision —
   the no-free-tier / card-required-trial / per-box substance is already
   decided (NEEDS_USER.md), the provider choice and its consequence are not.
   R2's implementation works around this with the operator's current
   default; it does not resolve it.
2. **Muse CLI auth must be proxy-key-based, never OAuth.** The operator's
   device-code login (`~/.config/muse/auth.json`) does not transfer to
   tenants and must never be baked into the image. The tenant path is the
   inference proxy's swapped credential; the refresh/re-auth path is an
   operator runbook, never a tenant-interactive flow.
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
multi-tenant pieces it injects into (H9/H10/H11) don't exist yet, and the
probe's exact command is deliberately left to the feature run. The external
precedent (E2B templates, PuppyOne's build/connect split) is market practice
for task-scoped sandboxes, not a controlled experiment on Muse-as-customer —
the R7 pilot remains the validation path for the transfer.
