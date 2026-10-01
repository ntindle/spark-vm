# harness — pre-seeded harness tooling (R2)

Implements the executable half of the R2 pre-seeded-harness contract
(`docs/PRE_SEEDED_HARNESS_RESEARCH.md`): the golden-image manifest and the
`<harness-auth-probe>` from the R1 first-ten-minutes contract
(`docs/FIRST_TEN_MINUTES_SPEC.md` §5).

## What's here

- **`harness-auth-probe`** — the non-interactive harness auth check. Run as
  `</dev/null timeout 10 <harness-auth-probe>`; exit 0, zero prompts.
  Verifies (a) the tenant runtime's model calls route through the inference
  proxy with the credential swapped in, then (b) confirmd liveness with
  misbinding detection: the probe requires confirmd's own 403 denial shape
  (`forbidden: <reason>` body + `confirmd/1` Server header, GitHub #160),
  not just any HTTP response — a port grabber or misbound service answering
  on the confirmd port must not certify the approvals path. This catches
  accidental misbinding at the gate, not an adversary who controls the port.
  Two modes: `gate` (image-build gate, against the public echo fixture —
  asserts the exact `Authorization: Bearer` wire shape and that the
  `hsurr:` placeholder never reaches the origin in any recorded field —
  the echo fixture records the full request (method, raw path incl.
  query, complete header set, sha256 of the body), so a placeholder
  leaking through a second header, a query parameter, or the request
  line fails the gate even when the Authorization header looks right;
  GitHub #157) and `provision`
  (live tenant box, against the real provider — asserts the provider
  accepted the swapped key). See the script header for the full env
  contract. Timeouts are mode-aware (GitHub #158, #159): gate keeps the
  6s CLI budget (a hang against a localhost fixture fails the gate per
  R1 §5) under a self-enforced 10s wall clock; provision gets a 25s CLI
  budget (TLS, cold model endpoints, and inference latency can exceed 6s
  on a healthy box) under a self-enforced 45s wall clock — provision-mode
  slowness is reported as slowness, never misdiagnosed as a bad
  credential. Wall-clock expiry and an external SIGTERM (e.g. the
  invoker's own `timeout 10` firing) exit 1 with a named message, so the
  probe process itself never dies as a bare 124 — every probe termination
  stays inside the documented 0/1/2/3 contract. (An invoker that still
  wraps the probe in an external `timeout` sees that wrapper's own 124/143
  status unless it passes `--preserve-status`; that is the wrapper's
  report, not the probe's.)
  `PROBE_CLI_TIMEOUT_S` / `PROBE_WALL_CLOCK_S` are test-facing budget
  overrides; the wall clock always wins. Never handles a real secret: it
  names only `hsurr:<name>` placeholders.
- **`generate-image-manifest.sh`** — emits the golden-image manifest JSON
  for the current checkout: repo SHA as `image_version`, the baked-component
  list, registry paths, unit names, and the `injector_expect` block the
  provision-time injector preflights against.
- **`check-image-manifest.sh`** — the injector preflight. Fails closed on
  schema mismatch, missing fields, or `image_version` drift vs
  `--expect-version` (defaults to the current checkout's HEAD; the
  injector passes its own pinned SHA).
- **`scan-baked-secrets.sh`** — gate-time negative scan enforcing the
  never-bake-values rule (GitHub #154): real secret shapes (PEM private
  keys, AWS/GitHub/OpenAI/Anthropic token shapes) must not appear in any
  baked file, credential-shaped filenames (`id_rsa`, `.env`,
  `auth.json`, ...) must not exist, and the credential value dirs
  (`home/swapd/secrets`, `home/swapd/inference-secrets`) must hold no
  non-empty value except the allowlisted public gate-fixture dummy.
  Pattern list in `baked-secrets-patterns.txt` (reviewed like code).
  Exit 0 clean, exit 1 gate refusal with per-hit report, exit 2 bad
  invocation. Wired as Steps 0b (pre-fixture refusal) and 5b
  (post-teardown pre-publish verdict) of
  `docs/GOLDEN_IMAGE_GATE_PROCEDURE.md`; Step 5b re-scans the same
  target as Step 0b. Prunes the top-level pseudo-filesystems and
  `__pycache__` / `.pytest_cache` dirs, never flags its own pattern
  file when the target contains it, and warns loudly on stderr about
  unreadable walk entries (skipped fail-open).

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
- **`key_identity.py`** — SSH-key-as-account identity primitives (GitHub
  #446, slice S1): parses OpenSSH public-key lines structurally (the
  algorithm embedded in the blob must equal the outer key type for every
  known type, plus 32-byte pubkey checks for the ed25519 variants),
  computes the OpenSSH `SHA256:` fingerprint (byte-identical
  to `ssh-keygen -lf`), derives a stable one-way `acct_<16 hex>` account id
  from the fingerprint (same key → same id; a new key is a new account —
  rotation-as-new-identity until the claim story ships), and emits the
  first-connect agent manifest (account id, fingerprint, expiry, claim link,
  policy) as JSON. Stdlib only, no state, no network — the
  fingerprint→account registry and same-key-resumes-same-box state are later
  slices; that registry slice is what will fill `claim_url`, `vm_endpoint`,
  and `box_id` (this slice emits the slots). `expires_at` is `None` for
  now: key-identity accounts do not expire; claim-link validity will be set
  by the claim/upgrade slice. One-key-one-identity is accepted for
  self-hosted and agent-created accounts; the hosted sybil policy is still
  an open question (see #446). Run
  `python3 key_identity.py <pubkey-file>` to print a key's manifest.
  Covered by `test_key_identity.py` (fingerprint vectors pinned
  to real `ssh-keygen -lf` output).
- **`key_registry.py`** — SSH-key-as-account registry (GitHub #446, slices
  S2 + S2.5 + S3): the stateful half S1 points at. A per-host fingerprint→account
  record store (`$XDG_STATE_HOME/spark-vm/key-registry`, override with
  `--registry-root`, either side of the subcommand) with created/last-seen
  timestamps and box binding — the storage foundation for "same key ->
  same box" resumes: first connects register the key, later connects look
  the fingerprint up. Single JSON file, atomic writes (`O_EXCL` temp +
  `os.replace`), lockdir mutual exclusion (stale locks reclaimed via pid
  check), corrupt stores fail closed rather than silently rebuilding,
  `0600`/`0700` modes. No secrets, no key material — records hold public
  fingerprints, one-way derived account ids, and claim-code SHA-256 hashes
  (never plaintext codes). Idempotent `register`
  (explicit `--box-ref` rebinds; omitting it leaves the binding alone; an
  empty `--box-ref` is rejected), plus `lookup`, `touch`, `bind`,
  `remove`, a registry-issued `manifest` (fills the S1-promised `box_id`
  slot), JSON `status`, `rotate` (slice S2.5: operator-held-key
  rotation — the new key registers as a new account per the
  identity-is-the-key policy, the old record keeps a forward link, the
  box binding carries over, and a bounded lineage journal records the
  rotation), and `claim-issue` / `claim-redeem` (slice S3: single-use
  claim codes with expiry — the key-loss upgrade path; the code is shown
  once, the store keeps only its hash). Stdlib only, no network. Covered
  by `test_key_registry.py` (66 tests incl. a threaded contention test,
  stale-lock/corrupt-store fail-closed checks, and the claim-protocol
  suite). Design note:
  `docs/KEY_IDENTITY_REGISTRY.md`.

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
   design), so the image-build gate owns that teardown pre-publish.
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

Dependency: `harness/proxy_match.py` must travel with the injector
(same directory). It is the single shared mirror of the proxy's
`_host_in_list` / `_parse_ssrf_allow` used by the teardown,
allowlist, and key-assertion checks; `harness/test_proxy_match.py`
pins it against the real proxy functions with a drift tripwire. The
injector fails closed if the helper is absent.

Prints exactly one JSON inject report on stdout; all progress and
refusal diagnostics go to stderr. The report's `steps` map reads
`"ok"` per completed step (`fixture_teardown` reads `"ok"` with the
absent/removed detail in `fixture_teardown_detail`); identity and
confirmd attribution read `"deferred (H9)"` / `"deferred (H10)"` and
are named in the `deferred` list when their inputs are absent. The
control plane gates box-live on the manifest, fixture_teardown,
inference_key, swapd_ca, and probe steps reading `"ok"`. Covered by
55 hermetic tests
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
