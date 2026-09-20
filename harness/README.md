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

## Fixture lifecycle

The fixture binds `llm-api` to the loopback echo host, allowlists
`127.0.0.1` in `inference-hosts.allow`, **and** exempts it in the
inference proxy's own `inference-ssrf.allow`. That binding must NEVER
coexist with a real credential: after the gate passes, the echo host MUST
be removed from `inference-hosts.allow` AND from `inference-ssrf.allow`,
and the `llm-api`→echo-host binding MUST be unbound — by the image-build
gate before the image is published, or by the provision-time injector
before it installs the real tenant key. Whichever stage runs last owns
the teardown. The gate is only safe because the fixture dummy is public
(`GATE-FIXTURE-DUMMY-NOT-A-SECRET`, baked into this repo on purpose);
the teardown is what keeps it safe once a real key exists. **Never run
`install-gate-fixture.sh` on a box holding a real credential** (it
refuses, but don't rely on the guard alone), and never install a real
credential with it (real keys travel the human-only grant-writer path,
SETUP.md "Inference-model recipe").

## Still to come (next feature slices)

- **Provision-time injector** — implements the research §4 inject list
  (tenant identity, inference credential by-name reference, fresh swapd
  CA, confirmd tenant attribution, first-task slot) against the H4
  `provision` interface, with the manifest preflight above.
- **Image gate** — refuses to publish the image when the gate-mode probe
  fails (the PuppyOne rule).

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
