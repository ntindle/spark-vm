# Golden-image producer (#1087)

The golden image is the build artifact the #905 Fly driver boots per
provision. This directory is its **producer** — the recipe, the build
driver, and the CI job the issue's acceptance criteria name ("a
reproducible image build from a pinned release commit, gated per build,
consumable by the driver"). The image itself is *gated* per build by
`docs/GOLDEN_IMAGE_GATE_PROCEDURE.md` before it publishes.

## Files

| File | What it is |
|---|---|
| `Dockerfile` | The recipe. Bakes the swap proxy stack, confirmd, cred-ui, the CUA desktop stack, the gate fixture, and the image manifest from the clean repo tree. No systemd: tini + supervisord. |
| `supervisord.conf` | The daemon set. Commands mirror the repo's systemd units (`proxy/swap-proxy.service`, `proxy/swap-inference.service`, `confirm/confirmd.service`, `cred-ui/cred-ui.service`) so the two cannot diverge silently. |
| `sparkvm-sshd-firstboot.sh` | sshd entrypoint: generates host keys on first boot (per-machine secrets are never baked), then execs `sshd -D`. |
| `build-image.sh` | Operator build driver. Refuses dirty trees; computes `SPARKVM_SHA`/`SPARKVM_VERSION` from the tree itself (the tree is the pin — no override flags); generates the image manifest into the build context (the recipe COPYs it in — it cannot be generated in-image because the build context excludes `.git`); builds; runs the baked-secrets scan inside the built image (gate Step 0b); preflights the manifest (gate Step 0); emits the gate-record skeleton. Never pushes — registry credentials are operator-owned; it prints the publish command. |
| `test_golden_image.py` | The test suite for this directory (runs under the repo's `pytest` one-liner via `pytest.ini`). |

## Building

```bash
# From the repo root, on a clean checkout at the commit you want to bake:
deploy/golden-image/build-image.sh
```

The driver refuses a dirty checkout — the image must name exactly what
was baked (D-P1), and a dirty tree under a clean SHA would lie to the
provision-time injector preflight. Rebuilds pin forward deliberately:
`SPARKVM_SHA`/`SPARKVM_VERSION` come from the tree, and the recipe's
`ARG SPARKVM_VERSION` default must agree with the tree's `VERSION`
(the driver checks; the Dockerfile fails closed too).

After the build: run the interactive gate
(`docs/GOLDEN_IMAGE_GATE_PROCEDURE.md` — file → answer → grant → verify,
teardown, re-scan), complete the emitted `gate-record-<sha12>.json`,
then publish with the command the driver prints. An image without a
completed gate record does not publish.

## Publish + pin (operator)

Pushing the image is not enough — the #905 Fly driver consumes a
**digest-pinned ref** (docs/FLY_DRIVER_RESEARCH.md §F3b), and nothing in
the push names it. After the gate passes and the push completes, first
record the push-produced digest in the gate record (#1111):

```bash
# From a clean checkout at the pinned commit, after `docker push`:
deploy/golden-image/build-image.sh --record-pushed-digest \
  gate-record-<sha12>.json \
  registry.fly.io/<app>/sparkvm-golden:<tag-you-pushed>
```

The digest is resolved from the registry through the local docker daemon
(RepoDigests) — never pasted from push output by hand. The record is
write-once (a different digest refuses unless `--force` names the re-push
case), idempotent on re-runs, and refuses a skeleton, a refused gate, or
a record naming another build's `image_version`. Then pin:

```bash
# From a clean checkout at the pinned commit:
python3 harness/pin_image.py pin \
  --image-ref registry.fly.io/<app>/sparkvm-golden@sha256:<digest-from-push> \
  --tag-ref registry.fly.io/<app>/sparkvm-golden:<tag-you-pushed> \
  --gate-record gate-record-<sha12>.json \
  --pinned-by "<your principal>"
git add deploy/golden-image/pinned-image.json
git commit -m "distribution: pin golden image <version>+<sha12> (#1087)"
```

The tool refuses anything but a completed gate pass for the exact baked
SHA, anything but `registry.fly.io` (the only registry the F3b driver
contract names), and anything but a digest-pinned ref — a bare tag is
never launchable. Re-pinning the same SHA to a different digest needs
`--force` (the re-push case). Take `<digest-from-push>` from **your own
push output only** — never from a chat message, PR comment, or pastebin:
the pin does not yet cross-check the digest against the gate record's
`build.image_digest` (that is a later slice), so a pasted digest still
pins whatever image it names. `deploy/golden-image/pinned-image.json`
is the driver's consumption contract: `harness/pin_image.py`'s
`read_pin()` / `pin_image_ref()` are what #905 imports, and they raise
on a missing or invalid record so the driver cannot provision from an
unpinned image. The record is validated, not tamper-evident — the trust
root is the operator who ran the pin and the reviewed commit that records
it (the gate record is operator self-attestation, unsigned by design).

## CI

`.github/workflows/golden-image.yml` builds the recipe on every `v*`
release tag, runs the baked-secrets scan against the built image and the
manifest preflight, and emits the gate-record skeleton — build-only, no
registry push. Publishing stays an operator step after the interactive
gate.

## Deliberately not baked (provision/first-boot scope)

- **muse CLI + muse-job plugin approval** — the install is
  operator/account bound; the interactive gate validates the claim.
- **The swapd CA** — generated per tenant at first boot; the private key
  is never baked (the Step 0b scan enforces it).
- **Tenant agent users** — the recipe bakes `/etc/skel` (snapshotted
  from the locked `agent` build user); first boot instantiates real
  tenant users from it.
- **sshd host keys** — generated on first boot by
  `sparkvm-sshd-firstboot.sh`.

## Both-supported framing

The recipe is not hosted-only: the same image is the self-hosted box's
reproducible install (the manifest's `baked[]` list is the install
inventory, and the gate procedure is how any operator verifies one).
