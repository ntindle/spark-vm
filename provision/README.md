# provision/

Provision-time harness tooling for spark-vm (the R2 feature track,
`docs/PRE_SEEDED_HARNESS_RESEARCH.md`). This directory will grow the
golden-image manifest, the provision-time injector, and the image-build
gate; today it holds the first slice: the harness auth probe and its
gate fixture.

## `harness-auth-probe`

R2 §5's `<harness-auth-probe>`, concretely. Run it exactly like this:

```bash
</dev/null timeout 10 provision/harness-auth-probe
```

Exit 0, zero prompts, stdin closed. Any prompt, hang, or timeout means the
box fails the harness check: report and stop. The probe never improvises
credentials, never walks anyone through a login, and never reads stdin
(it refuses outright if stdin is a TTY).

What it verifies, in order:

1. **The inference path.** A GET carrying `Authorization: Bearer
   <placeholder>` (default `hsurr:llm-api`) goes through the inference
   proxy (default `http://127.0.0.1:18081`); the proxy must swap the
   placeholder for the installed credential. Two expectation modes
   (`HARNESS_PROBE_EXPECT`):
   - `echo` (default, gate mode): the upstream is the public echo
     fixture. Passes when the echo host answers 200, the Authorization
     it saw is *not* the placeholder, and the placeholder string appears
     nowhere in the echoed request. Proves the full swap path end to end
     with zero real credentials.
   - `auth-accepted` (provision mode): the upstream is the real
     provider. Passes on any status except 401/403 — the swapped
     credential was accepted. Point `HARNESS_PROBE_PATH` at a path that
     is auth-gated; an open path proves nothing.
2. **confirmd answers.** An HTTPS GET to `/api/version` on the confirmd
   service (default `https://<tailscale-ip4>:8443`). Any 2xx/3xx/4xx
   response (200, 401, 403 — confirmd is owner-authenticated, so a refusal
   is still an answer) proves the daemon is alive and serving; a 5xx
   means "alive but broken" and fails the check, as do connection
   refused / timeout / TLS failure. The TLS check is
   unverified on purpose: this is a liveness check, not an identity
   check — the tenant's browser does the real auth.

Stdout carries one JSON report line (`{"ok": ..., "checks": {...}}`);
human-readable one-liners go to stderr. Exit codes: 0 all checks passed,
1 a check failed, 2 misconfigured / refused to run, 3 internal deadline
hit (default 9 s, inside the external `timeout 10`).

Configuration is all environment (see the probe's docstring for the full
list). The probe drops `no_proxy`/`NO_PROXY` for its own process: check
1 *must* traverse the inference proxy, and an ambient bypass entry would
silently turn it into a direct connection. The probe handles only
placeholder *names* and the public gate-fixture dummy — never real
secret values.

## `install-gate-fixture.sh`

Installs the public, non-secret gate fixture through the existing narrow
writers only: the dummy `llm-api` credential, its `bearer_header`
registry placement, the echo host in `inference-hosts.allow`, then runs
the probe in gate mode to prove the fixture works. Idempotent; the proxy
hot-reloads registry/hosts per request, so no restart is needed.

**Never install a real credential with this script.** The fixture dummy
(`GATE-FIXTURE-DUMMY-NOT-A-SECRET`) is public by design — baked into the
repo and the image on purpose. Real tenant credentials travel the
human-only grant-writer path (SETUP.md "Inference-model recipe").

### Fixture lifecycle

The fixture binds `llm-api` to the public echo host **and** allowlists
that host in `inference-hosts.allow`. That binding must NEVER coexist
with a real credential: after the gate passes, the echo host MUST be
removed from `inference-hosts.allow` and the `llm-api`→echo-host binding
MUST be unbound — by the image-build gate before the image is published
(roadmap item 4), or by the provision-time injector when it installs the
real tenant key (roadmap item 3). Whichever stage runs last owns the
teardown. If the binding survived onto a box holding a real key, any
request to the echo host carrying the placeholder would swap in the real
tenant key and ship it to a public echo server. The gate is only safe
because the fixture is public; the teardown is what keeps it safe once a
real key exists.

### Limitations

- Gate mode depends on a public third-party echo host (default
  `httpbin.org`): the image-build gate needs outbound internet at build
  time. The dummy credential is public, so no secret is exposed — but
  the network dependency is real. Override with `HARNESS_GATE_ECHO_HOST`
  / `HARNESS_PROBE_UPSTREAM` for air-gapped builds.
- The confirmd check is liveness, not health-depth: 2xx/3xx/4xx pass, 5xx
  fails, and it does not verify the approvals path end to end (filing an
  approval still needs the tenant's browser auth).

## Roadmap (R2 handoff order)

1. ~~`<harness-auth-probe>` per §5~~ — this directory (done)
2. Golden-image manifest (what bakes, versioned, checksummed)
3. Provision-time injector implementing §4's inject list against the H4
   `provision` interface
4. Golden-image gate refusing broken images (runs the probe; gate mode
   via `install-gate-fixture.sh`)
5. The R1 first-run script green against the result
