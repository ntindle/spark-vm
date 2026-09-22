# harness — pre-seeded harness tooling (R2)

Implements the executable half of the R2 pre-seeded-harness contract
(`docs/PRE_SEEDED_HARNESS_RESEARCH.md`): the golden-image manifest and the
`<harness-auth-probe>` from the R1 first-ten-minutes contract
(`docs/FIRST_TEN_MINUTES_SPEC.md` §5).

## What's here

- **`harness-auth-probe`** — the non-interactive harness auth check. Run as
  `</dev/null timeout 10 <harness-auth-probe>`; exit 0, zero prompts.
  Verifies (a) the tenant runtime's model calls route through the inference
  proxy with the credential swapped in, then (b) confirmd liveness.
  Two modes: `gate` (image-build gate, against the public echo fixture —
  asserts the exact `Authorization: Bearer` wire shape and that the
  `hsurr:` placeholder never reaches the origin) and `provision`
  (live tenant box, against the real provider — asserts the provider
  accepted the swapped key). See the script header for the full env
  contract. Never handles a real secret: it names only `hsurr:<name>`
  placeholders.
- **`generate-image-manifest.sh`** — emits the golden-image manifest JSON
  for the current checkout: repo SHA as `image_version`, the baked-component
  list, registry paths, unit names, and the `injector_expect` block the
  provision-time injector preflights against.
- **`check-image-manifest.sh`** — the injector preflight. Fails closed on
  schema mismatch, missing fields, or `image_version` drift vs
  `--expect-version` (defaults to the current checkout's HEAD; the
  injector passes its own pinned SHA).

- **`install-gate-fixture.sh`** — installs the gate fixture the `gate`-mode
  probe asserts against: the public dummy inference credential under the
  proxy's single fixed credential name (`llm-api`) through the narrow
  writers, its `bearer_header` placement, the loopback echo host bound in
  the inference registry and allowlisted in `inference-hosts.allow`, and
  the loopback host exempted in the inference proxy's own
  `inference-ssrf.allow` (never the main proxy's shared file), then
  starts the loopback echo fixture and runs the probe in gate mode to
  prove the wiring. Idempotent; safe to re-run. Fail-closed: refuses to
  run if `llm-api` already holds a non-fixture credential. The guard
  verifies two things without ever reading the stored value: the registry
  shows `llm-api` bound ONLY to the loopback echo host, AND a blind
  compare (`proxy/cred-store-verify-inference`) confirms the stored
  value is the public fixture dummy. That second check is what makes
  the guard honest — a signature-only check could not distinguish a
  previous fixture run from a real tenant key installed without the
  documented teardown (the registry would show the same signature in
  both cases), and overwriting it would destroy the box's only
  inference key. The echo
  fixture and its log are gate-scratch (started and killed by the
  installer, never a service).
- **`echo-fixture.py`** — the echo origin the installer starts: a
  loopback-only HTTP server that appends one
  `{"method","path","authorization"}` JSONL record per request to the log
  and answers 200. Same record format as the hermetic echo server in
  `test_probe.py`.
- **`provider_iface.py`** — the H4 provider-agnostic driver contract: the
  six verbs (`provision` / `status` / `suspend` / `dial` / `ssh_info` /
  `destroy`, `snapshot` reserved), the validated lifecycle state machine
  (`provisioning | running | suspending | suspended | waking | stopping |
  stopped | failed | destroyed`, `degraded` as an orthogonal health flag),
  wake-wait `dial()` semantics, the per-shape capability flags
  (`supports_suspend`, `memory_resume` axis), the billing-facing
  `retention` descriptor, the per-tenant `auto_resume` gate, and the
  fail-closed `public_ingress: false` spec invariant with a
  driver-attested network-isolation check, the park-mechanics axes
  (`wake_reprovisions` per-shape flag + `wake_kind` resume-path surface
  for RunPod-style backends whose "suspend" is park), and a note that the
  per-`vm_id` lifecycle is provisional on H11's isolation answer. Covered by
  `test_provider_iface.py` (41 contract tests incl. a fake in-memory
  driver exercising the full lifecycle).

## Fixture lifecycle

The fixture binds `llm-api` to the loopback echo host, allowlists
`127.0.0.1` in `inference-hosts.allow`, **and** exempts it in the
inference proxy's own `inference-ssrf.allow`. That binding must NEVER
coexist with a real credential: after the gate passes, the echo host MUST
be removed from `inference-hosts.allow` AND from `inference-ssrf.allow`
(by the image-build gate before the image is published — the injector
cannot remove allowlist lines; production sudoers is append-only by
design), and the `llm-api`→echo-host binding MUST be unbound — by the
image-build gate pre-publish, or by the provision-time injector before
it asserts/probes the real tenant key. The operator installs the real
key through the human-only grant-writer path BEFORE the injector runs;
the injector asserts and probes, never installs. The gate is only safe because the fixture dummy is public
(`GATE-FIXTURE-DUMMY-NOT-A-SECRET`, baked into this repo on purpose);
the teardown is what keeps it safe once a real key exists. **Never run
`install-gate-fixture.sh` on a box holding a real credential** (it
refuses, but don't rely on the guard alone), and never install a real
credential with it (real keys travel the human-only grant-writer path,
SETUP.md "Inference-model recipe").

## Still to come (next feature slices)

- **First-task slot properties** — the §4 inject list's remaining
  item, deferred to the R1 first-run slice (it belongs to what the box
  does first, not to credential injection).
- **Image gate** — refuses to publish the image when the gate-mode probe
  fails (the PuppyOne rule).

## Provision-time injector (`inject-provision-state.sh`)

Runs at first boot of the hosted agent VM (invoked by the H4
provisioning driver) and owns the provision-time half of the fixture
lifecycle above:

1. Preflights the golden-image manifest against the operator-pinned
   `INJECT_IMAGE_VERSION` (via `check-image-manifest.sh`) and fails
   closed on any drift, before box-live.
2. Tears down the gate fixture: unbinds `llm-api`→echo-host through the
   narrow registry writer, then fails closed on any echo-host residue in
   `inference-hosts.allow` or `inference-ssrf.allow`. The injector cannot
   remove allowlist lines (production sudoers is append-only by
   design), so the image-build gate owns that teardown pre-publish —
   whichever stage runs last owns it.
3. Asserts a real inference credential: registry binding of `llm-api`
   (`bearer_header`) to a non-loopback host, plus a blind
   `cred-store-verify-inference` compare proving the stored value is
   NOT the public fixture dummy. The stored value is never read,
   never written, never printed — assert, never handle.
4. Requires a fresh per-tenant swapd CA (`mitmproxy-ca.pem`).
5. Installs tenant identity when `INJECT_IDENTITY_DIR` is set (H9
   input contract): an `authorized_keys` file only, strict public-key
   shape validation — private-key material is refused, fail-closed.
   Deferred and loudly reported when absent. (Research §4 scopes H9
   identity as "keys/certs"; this v1 seam is authorized_keys-only — the
   H9 slice must grow the contract if it needs TLS/SSH certs.)
6. Records tenant attribution when `INJECT_TENANT_ID` is set (H10
   input contract): a validated tenant id plus the pinned image
   version, for the per-tenant approvals slice. Deferred and loudly
   reported when absent.
7. Runs `harness-auth-probe` in `provision` mode so the injected key
   is proved against the real provider; a probe failure maps to
   `provisioning-failed` (box-live must not flip).

Prints exactly one JSON inject report on stdout; all progress and
refusal diagnostics go to stderr. The report's `steps` map reads
`"ok"` per completed step (`fixture_teardown` reads `"ok"` with the
absent/removed detail in `fixture_teardown_detail`); identity and
confirmd attribution read `"deferred (H9)"` / `"deferred (H10)"` and
are named in the `deferred` list when their inputs are absent. The
control plane gates box-live on the manifest, fixture_teardown,
inference_key, swapd_ca, and probe steps reading `"ok"`. Covered by
25 hermetic tests
(`test_inject_provision_state.py`) mirroring the install-gate-fixture
hermetic contract: fake writers, a fake sudo that asserts `-u swapd`
and denies `tee`/`ls`, a fake swap proxy resolving `hsurr:`
placeholders, a provider stub recording `Authorization` headers, and a
stub confirmd.

## Known validation points

- The probe routes the CLI through the inference proxy via `HTTPS_PROXY`
  env (forward-mode mitmdump + per-host registry matching). Whether the
  Muse CLI honors proxy env vars is proven by the gate-mode integration
  run: if it does not, no records reach the echo log and the probe fails
  closed naming the routing attempted — investigate, do not work around.
- In `provision` mode the `Bearer` wire shape is asserted implicitly
  (the provider accepted the swapped key); the explicit assertion lives
  in `gate` mode via the echo log.
- The echo fixture's swapped dummy value is public and non-secret by
  design; it travels in `PROBE_EXPECTED_SWAPPED` in the clear.

## Tests

`python3 -m pytest harness/` — hermetic (fake `muse` CLI, in-process echo
server + header-rewriting forward proxy, no mitmproxy, no real CLI).
