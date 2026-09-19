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

## Still to come (next feature slices)

- **Gate fixture installer** — installs the public dummy inference
  credential (`gate-dummy`) into the inference registry and the echo host
  into the gate-scoped allowlist, starts the echo server, and runs the
  probe in gate mode. Includes the gate-fixture cleanup (remove the
  echo-host allowlist entry at box-live).
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
