# Fly driver design-ahead (#905 build input)

**Vision vs state for the #905 Fly Machines driver build** — pinned to
main `48a8030` for all in-repo claims. Baseline: the 2026-10-06
provisioning+metering convergence pass
(`docs/PROVISIONING_METERING_CONVERGENCE_2026-10-06.md`, main `645e814`).
This doc answers one question: *what can the #905 build now assume, and
what genuinely-new gaps must it close or file around?*

Doc-first; honesty rules apply (`docs/POSITIONING.md`): everything below
is **current state and work to do**, not promises. The hosted product is
not live.

## 1. The vision, restated in one paragraph

The #906 orchestrator consumes an invite claim and calls
`driver.provision(spec)`; the Fly driver creates the per-tenant app,
volume, and machine from the digest-pinned golden image, seeds identity
through machine-config env, and returns a connection bundle whose host-key
fingerprint is attested — never TOFU. The box's first-boot hook enrolls
via the plane-attested pairing token (#907/#1108), meters itself (#1047),
and the spend ledger attributes burn to the tenant lineage (#1074) with
pre-provision cap checks refusing over-budget claims (#1075). Tracked on
#851 (provisioning); the driver is #905.

## 2. What moved since 2026-10-06

- **F-D1 — #1087 closed 2026-10-07: the golden-image producer is
  in-repo.** `deploy/golden-image/` ships the recipe (`Dockerfile`), the
  build driver (`build-image.sh`: refuses dirty trees, computes
  `SPARKVM_SHA`/`SPARKVM_VERSION` from the tree, runs the baked-secrets
  scan in-image, never pushes — registry credentials stay operator-owned),
  the sshd first-boot wrapper (`sparkvm-sshd-firstboot.sh`: generates host
  keys on first boot, never baked), `supervisord.conf` (tini +
  supervisord; commands mirror the repo's systemd units "so the two
  cannot diverge silently"), the image-manifest tooling, and a test suite.
  The image bakes the swap proxy stack, confirmd, cred-ui, and the CUA
  desktop stack.
- **F-D2 — #1176 closed 2026-10-08: the golden-image gate now runs on
  release tags** (the GITHUB_TOKEN tag-push fix). The per-build gate
  (`docs/GOLDEN_IMAGE_GATE_PROCEDURE.md`) is wired into the release
  workflow.
- **F-D3 — FLY_DRIVER_RESEARCH open item 1 (supervision redesign)
  resolved by #1087.** The non-systemd supervision the research named as
  the "true shared prerequisite" is the shipped tini + supervisord set.
- **F-D4 — #1107's contract half is on main.** `harness/provider_iface.py`
  carries D-O1: the claim-binding idempotency key
  `(tenant_id, claim_id, attempt_n)` (canonical-typed, fail-closed),
  `list_boxes()` with `BoxIdentity`, and the provision() dedupe contract
  (same-key retry returns the existing box — never a second box, never an
  error; the key rides provider-side metadata). #1107 stays open; the
  driver-side dedupe behavior is #905's build scope.
- **F-D5 — #1108 filed (open): the attestation-token wire contract.**
  256-bit random base64url, minted by the plane at provision-record
  creation; the owner-auth create endpoint returns the plaintext once;
  the plane stores only the hash (D-P2); the plaintext transits exactly
  twice (plane→orchestrator, orchestrator→box env). TTL, consume
  semantics, and replay behavior are #1108's build scope — the driver
  only carries the opaque value.
- **F-D6 — #1089 filed (open): the provision-record store pin.** D1,
  plane-readable (D-P2); one record, two consumers (G51.3 attestation
  validation, #1074 ledger ingestion).
- **F-D7 — #1075 (open) names its driver dependency explicitly:** the
  cap-check's projected-cost function "consumes #905's machine-size data
  ... interim static size→cost table". The driver build owns the
  size→cost model (decision D-D4).
- **F-D8 — FLY_DRIVER_RESEARCH's `parked` language is stale against the
  shipped contract.** `harness/provider_iface.py` adjudication #1
  superseded the `parked` state: a driver-requested suspend *always*
  surfaces as `suspended` regardless of substrate mechanism (on the Fly
  reference shape that is a cold stop under the hood — the caller asked
  for suspend and the box will be woken); warm-vs-cold rides the
  `memory_resume` / `wake_kind` axes, never the state name. The
  research's F2/F3 `stopped → parked` row and its "Proposed
  interface-level contract language" `parked` definition predate the
  contract. **The driver build follows `provider_iface.py`; the research
  doc needs a dated supersession note** (disposition: the #905 build's PR
  carries the note — this doc records the pin so the build doesn't
  re-litigate it).
- **F-D9 — G51.4's first-boot identity-seeding hook is unbuilt** (new gap
  G-D1, filed). Nothing in the golden image reads `SPARKVM_BOX_ID`,
  `SPARKVM_PLANE_URL`, or the attestation token from machine-config env;
  nothing fails closed when the vars are absent; nothing triggers pairing
  init. #905's body claims the contract ("machine-config env read by a
  first-boot hook"), but the hook exists in neither the image nor the
  repo — the only in-repo references to the vars are `deploy/auto-deploy.sh`
  and `fleet/` (the self-hosted path, not the image).
- **F-D10 — `ssh_info()` host-key attestation has no mechanism** (new gap
  G-D2, filed; decision D-D3). `provider_iface.py` demands the VM
  host-key fingerprint "attested over the authenticated provisioning
  channel — the Muse pins it, no blind TOFU"; FLY_DRIVER_RESEARCH F3
  repeats the requirement without a mechanism; the image generates host
  keys at first boot on its own rootfs with no report-back path. A
  driver that reads the fingerprint from anywhere the box reports it is
  TOFU with extra steps.
- **F-D11 — the /data-vs-baked volume-mount contract is unpinned** (new
  gap G-D3, filed). FLY_DRIVER_RESEARCH open item 3 still open. The
  reference shape is `COLD_ONLY` with an ephemeral rootfs (F1): a cold
  stop resets the rootfs to the image while the volume persists. Which
  box state must live on `/data` (enrollment, swapd state, confirmd
  pending/, heartbeat tick, generation/backoff files, audit buffer) vs
  the image is unanswered — and the driver's provision path must know
  where provision-time writes land.
- **F-D12 — the handoff-invariant residual is still open** (F6b open item
  8; not a new issue — operator-owned). The driver build cannot defer
  past its PR which branch it takes: (a) verify machine-exec can be
  disabled at handoff while start/stop/destroy still work, or (b) bring
  the operator-signed §6 invariant-5 revision. This design-ahead records
  the open decision; it does not pre-decide it.

## 3. The #905 build's input contract (decisions)

- **D-D1 — `harness/provider_iface.py` is the fixed build target.**
  Where FLY_DRIVER_RESEARCH's pre-contract language conflicts
  (`parked` mapping, `destroy(tenant_id)`), the contract wins. The
  research remains the provider-facts source (F1/F2/F4–F7 stand).
- **D-D2 — golden-image path only, at first.** The driver implements the
  golden-image provision path; the exec-install alternative (F1b) stays a
  documented alternative, not a second build. The image now exists and is
  gated per build — the "recommended path" premise the research
  conditioned on is satisfied.
- **D-D3 — host-key attestation: the driver mints, the image prefers.**
  At provision, the driver mints a per-machine ed25519 host keypair and
  injects the private key via machine-config env (`SPARKVM_SSH_HOST_KEYS`,
  alongside the D-D6 identity vars). The image's first-boot wrapper gives
  env-provided keys precedence over pre-existing self-generated keys (the
  current skip-if-present idempotency in `sparkvm-sshd-firstboot.sh` must
  change — otherwise a reimaged dev rootfs keeps the wrong identity) and
  keeps `ssh-keygen -A` only for non-hosted (self-hosted/dev) use; hosted
  provision fails closed when the driver cannot mint. Attestation holds by
  construction — `ssh_info()` reports the fingerprint of the key the driver
  minted, over the authenticated provision channel. Why this shape: the keys
  are per-machine, never baked into the shared image (the image's "never
  baked" rule holds); machine-config env is present before first boot (no
  ordering hazard with an exec-API file write) and persists across cold
  stops (verify at build time per #1204 — assumed from the machine-config
  model, unconfirmed against docs.machines.dev), so the fingerprint stays
  stable across wake. Load-bearing note: the park-style re-query rule never
  fires for the Fly shape (`wake_reprovisions=false`), so the driver never
  re-checks the fingerprint after a wake — env persistence across cold stops
  is the SOLE stability guarantee, and the #1204 build-time verification is
  not optional: if env does not persist, the fingerprint silently desyncs
  from the Muse's pin; ed25519 is the attested key (smallest, modern,
  sufficient for the pin). Known exposure:
  machine-config env is readable via the Machines API under the
  provisioning token — the same trust domain as the provision path itself,
  not a new one — and the Fly dashboard's machine-config view is an
  additional read surface for `SPARKVM_SSH_HOST_KEYS`. Open question for
  #1204: host-key rotation — the env holds a persistent private key with no
  rotation story yet.
- **D-D4 — the driver owns the size→cost model.** The reference shape's
  $/mo (performance-8x + 250 GB volume, operator-pinned region) and the
  F2 storage-only-billing suspended rate ship as driver-exposed data /
  operator config that #1075's projected-cost function consumes,
  replacing its interim static table.
- **D-D5 — region, digest-pinned image ref, and app-name prefix are
  operator config; the F6b token-minting half is #905 build behavior.**
  The driver takes region, the digest-pinned image ref, and the app-name
  prefix as config; it never defaults them. (F3b: the driver takes the
  pinned ref; the pipeline holds the push credential.) The per-app token
  lifecycle's minting half (F6b steps 1–2: org token creates
  `tenant-<id>`, immediately mints the per-app deploy token; provision
  steps run under short-lived machine-exec tokens or the per-app token —
  never the org token) is driver behavior the #905 build implements, not
  config. The handoff half (F6b steps 3–4: which token survives, with what
  scope) stays under D-D7's open branch.
- **D-D6 — machine-config env is the provision-time seeding channel.**
  `SPARKVM_BOX_ID`, `SPARKVM_PLANE_URL`, the attestation token (opaque to
  the driver; format per #1108), `SPARKVM_SSH_HOST_KEYS` (D-D3). All
  consumed by the G-D1 first-boot hook; the driver only carries them.
- **D-D7 — the #905 build's acceptance names its handoff branch.**
  F-D12's (a)/(b) is the one open decision this design-ahead does not
  make — the driver's PR states which branch it takes and verifies.
- **D-D8 — G51.4's tracking pin is amended, not silently rewritten.**
  `docs/BOX_PROVISIONING_GAP_ANALYSIS.md` (2026-10-03) pinned G51.4 as
  "tracked under the driver issue (G51.1), not a separate issue" — made
  before the golden image existed as a separate component. The
  golden-image leg of the contract re-tracks to #1203 (the hook is
  image-side, `deploy/golden-image/`; #905 is driver-side), with a dated
  amendment note at the original pin; the exec-install `/data` leg stays
  deferred with the F1b alternative per D-D2. #1203's acceptance is "closes
  G51.4's golden-image leg" — it does not retire the exec-install leg.

## 4. Genuinely-new gaps (filed)

- **G-D1** — golden-image first-boot identity-seeding hook: reads the
  D-D6 env vars, fails closed (no enroll, loud log) when absent, triggers
  pairing init presenting the attestation token. Filed as #1203 (p2,
  track:hosted-product, #851). #905 build input; closes G51.4's
  golden-image leg per the D-D8 tracking amendment (the exec-install leg
  stays deferred with F1b per D-D2).
- **G-D2** — host-key attestation mechanism per D-D3: driver mints +
  env-injects ed25519 host key; firstboot prefers env keys; hosted
  provision fails closed without them. Filed as #1204 (p2,
  track:hosted-product, #851). #905 build scope (ssh_info contract).
  **Build note 2026-10-09:** the golden-image half shipped (PR #1239) —
  `sparkvm-sshd-firstboot.sh` installs `SPARKVM_SSH_HOST_KEYS` (base64 of
  the OpenSSH ed25519 private key) with precedence over pre-existing
  self-generated keys, fail-closed on present-but-invalid (nonzero exit,
  no `ssh-keygen -A` fallback; set-but-empty counts as invalid),
  idempotent on fingerprint match, and writes a per-boot
  `/run/sparkvm/ssh_host_key.status` receipt (source/key_type/
  fingerprint_sha256). Install-step failures are explicitly fatal
  (the function's OR-list call context disables set -e for its body),
  the install resolves through D-V3 dangling symlinks via `readlink -f`,
  and the installed fingerprint is re-verified before the receipt is
  written. Machine-config env persistence across cold stops verified
  against the Fly stop/start model (config is server-side per-machine
  state — machines are stopped and restarted with env intact; the #905
  driver build re-confirms the load-bearing case). **Driver contract
  added:** the #905 driver MUST read back the receipt and fail the
  provision / mark the box unhealthy unless `source=env` and the
  fingerprint matches the minted key — otherwise a dropped env lets the
  box silently self-generate while the driver reports the minted
  fingerprint (split-brain). The driver half — minting, env injection,
  `ssh_info()` reporting the minted fingerprint, fail-closed provision
  without mint — stays #905 build scope; host-key rotation stays the
  open question.
- **G-D3** — /data volume-mount contract: inventory of box state that
  must persist on /data across cold stops vs the ephemeral rootfs;
  provision-time write targeting. Filed as #1205 (p2,
  track:hosted-product, #851). Consumed by the #905 build and the image.

## 5. Stay-open

#851 stays open. #905 (driver), #906 (orchestrator), #907/#1108
(attestation), #908/#1074–#1077 (spend caps), #1047/#1048 (metering),
#1089 (provision-record store), #1109/#1110 (orchestrator slices) remain
open. Nothing in this doc closes an issue; it pins what the #905 build
consumes.
