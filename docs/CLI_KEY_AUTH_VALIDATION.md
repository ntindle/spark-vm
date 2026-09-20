# Muse CLI static-key auth through the inference proxy's header-swap path — validation

Status: **VALIDATED** 2026-09-19 (experiment on spark-vm, hermetic — no real
secret, no provider contact, no quota burned).

Closes the highest-risk unvalidated assumption in
`docs/PRE_SEEDED_HARNESS_RESEARCH.md` §6.2: *"there is zero repo evidence the
Muse CLI supports static-key auth or custom base-URL/proxy routing."* There
is now direct experimental evidence, and the R2 feature run's
"validate-first" gate is lifted: the injector may assume the tenant Muse
authenticates with a static placeholder key through the inference proxy.

## The question

The R2 pre-seeded-harness design needs the tenant's `muse` CLI to
authenticate to the inference proxy (`swap-inference` on `:18081`) with a
static key, so that the proxy's header-swap substitutes the real provider
key on egress. The operator's box today uses a device-code OAuth login
(`~/.config/muse/auth.json`) — which must never be baked into a tenant
image — and the repo had no evidence the CLI accepted any static-key path
at all. If the CLI were OAuth-only, R2's injector and probe (§4–§5) would
collapse and the harness would need a different runtime.

## Method

Hermetic experiment on spark-vm (2026-09-19 ~17:00 CDT), Muse CLI 1.3.0
(`muse-build/1.3.0`, non-interactive). A stub HTTP server on
`127.0.0.1` recorded every request's method, path, and headers, and
answered 400 to everything. Three runs, one per static-key mechanism,
each with all proxy env vars unset (no MITM in the loop) and a placeholder
key (never a real secret; the stub never contacted the real provider):

1. `META_API_KEY=hsurr:test-placeholder timeout 25 muse exec --provider
   meta --base-url http://127.0.0.1:37661 --reasoning-effort minimal "ping"`
2. `printf %s hsurr:test-stdin-key | muse exec --provider meta
   --base-url http://127.0.0.1:37641 --api-key-stdin
   --reasoning-effort minimal ping` (key via stdin, prompt via argv)
3. `muse auth set` against a throwaway `HOME` (`~/keyauth-stub/fakehome`,
   real `~/.config/muse/auth.json` untouched): stored
   `hsurr:test-authset-key`, then a plain `muse exec` (no env key, no
   `--api-key-stdin`) under the same fake HOME against the stub.

The stub and its directory were removed from the box afterwards; the only
box state ever touched was the throwaway fakehome (deleted).

## Findings

- **F1 — The CLI accepts static API keys, three ways — all three
  empirically exercised** (`muse --help`, verified 2026-09-19):
  (1) `META_API_KEY` environment variable — `muse login --help` states
  *"META_API_KEY always takes priority over the account login"*;
  (2) `muse auth set --provider meta --api-key-stdin` (stdin-only, never
  argv/shell history; stored at `~/.config/muse/auth.json` under
  `providers.meta.api_key` — plaintext JSON);
  (3) `muse exec --api-key-stdin` (per-run key from stdin). The provider
  set is currently just `meta` (the only `--provider` value accepted),
  which is the provider the tenant path needs.
- **F2 — The key is sent as `Authorization: Bearer <key>` on every
  request observed.** All 12 captured requests in the `META_API_KEY` run
  and all 12 in the `--api-key-stdin` run carried
  `Authorization: Bearer <placeholder>` (both request shapes the CLI
  makes: `GET /muse-code/models` and `POST /responses`); the stored-key
  run's request (1 captured before the stub's 400 aborted the catalog
  fetch) carried `Bearer hsurr:test-authset-key`. Each placeholder
  arrived byte-identical — the CLI does not munge, quote, or case-fold
  it. (The stub answered 400 to everything, so successful-auth-path
  behavior — retries with a valid key, token refresh — is unobserved.)
- **F3 — `--base-url` overrides the provider base URL.** Requests arrived
  at the stub (including over plain `http://`, no TLS complaint), so the
  tenant runtime can point the CLI at the inference proxy's address
  directly. (The R2 probe and injector still choose the exact routing —
  env `HTTPS_PROXY` vs `--base-url` — this experiment only proves the
  override exists and is honored.)
- **F4 — This matches the inference registry's `bearer_header` placement
  exactly.** `proxy/swap_addon.py` documents (line 29) and implements
  (`_swap_basic_auth` fallback, `_auth_location`) that `bearer_header`
  "swaps only in an `Authorization: Bearer`" header — i.e. the registry
  was already written for precisely the wire format the CLI emits, and
  the inference proxy is header-only by construction (finding 31:
  prompt page content must never traverse credential insertion).
- **F5 — No OAuth credential is consulted at inference time when
  `META_API_KEY` is set.** The runs made their requests with no evidence
  the OAuth credential was used (`muse login --help`: *"META_API_KEY
  always takes priority over the account login"*; no browser
  code-approval flow was triggered). Untested: behavior with `~/.config/muse/auth.json`
  entirely absent — the experiment ran with the operator's `auth.json`
  present-but-unconsulted. The tenant image must prove the absent-file
  case: require the R2 `<harness-auth-probe>` (§5) to run on a golden
  image that genuinely lacks the file.

## Tenant-shape recommendation for the R2 feature run

Prefer provision-time `META_API_KEY=hsurr:llm-api` in the tenant's
environment over `muse auth set` in the image — **provided the H4
injector channel does not materialize a credential file in the tenant
filesystem.** Hypervisor/cloud-init env, container env, or a
provision-time process env qualify; a systemd drop-in, profile.d file,
or unit `EnvironmentFile` does not (those are credential-shaped files on
the box, possibly world-readable, and erase the recommendation's core
rationale — the injector design must name its channel). Structural
trade-offs, stated explicitly:

- Env **inherits into every child process** the CLI spawns (MCP servers,
  shell-outs, core dumps), widening in-tenant visibility of the value vs.
  a CLI-read credential file. Harmless here *only because* the value is
  a placeholder — the real key never touches the tenant box. State this
  as the reason the trade-off stays safe, not as an afterthought.
- Genuine advantage over `auth set`: rotation requires no in-tenant
  filesystem write — replace the injected value, restart the process;
  `auth set` would need a credential-file rewrite inside the tenant.
- `muse auth set` writes the key **plaintext** to
  `~/.config/muse/auth.json` (`providers.meta.api_key` — verified against
  a throwaway HOME); snapshotting or copying that home directory (H13
  suspend/wake, image capture) would carry a credential-shaped file
  around. Env injection avoids the file entirely (channel permitting).

Non-blocking for this turn: the R2 `<harness-auth-probe>` (§5) should
assert the `Authorization: Bearer` wire shape explicitly, so a future CLI
update that changes the auth scheme fails loudly at the probe instead of
silently passing the placeholder through unswapped.

## What this did NOT prove (kept open, non-blocking)

- The full round trip through the real `swap-inference` mitmproxy
  (placeholder in → real key out on egress). The swap side is covered by
  the proxy's own tests (`proxy/test_swap_addon.py`,
  `test_bug_inference_mode_header_only`); the client half is what this
  experiment adds.
- Behavior with `~/.config/muse/auth.json` entirely absent — the
  experiment ran with the operator's auth.json present-but-unconsulted
  (see F5). The absent-file case belongs to the R2
  `<harness-auth-probe>` on the real golden image.
- TLS-terminated routing. The *Bearer wire format* is TLS-independent
  (validated above); what is NOT validated is the CLI's trust of the
  proxy's MITM CA and TLS behavior through the real `swap-inference`
  instance on `:18081` — the experiment exercised zero TLS (plain
  `http://` stub, no proxy env vars). The load-bearing transfer risk is
  client-side trust of the proxy's CA (system trust store vs. bundled
  certs vs. pinning), which interacts with the still-open routing choice
  (HTTPS_PROXY CONNECT vs. direct `--base-url` TLS). Require the R2
  `<harness-auth-probe>` (§5) to exercise the real TLS-terminating
  proxy instance, not just the wire shape.
- Other subcommands (`muse mcp login` is OAuth — a separate flow,
  irrelevant to inference auth).

## Decision record

`PRE_SEEDED_HARNESS_RESEARCH.md` §6.2's highest-risk unknown is resolved:
**the Muse CLI supports static-key auth and emits exactly the
`Authorization: Bearer <placeholder>` wire format the inference proxy's
`bearer_header` placement swaps.** The R2 feature run's validate-first
gate is lifted — proceed to (1) golden-image manifest, (2) injector,
(3) `<harness-auth-probe>` per §5 (the probe must exercise the real
TLS-terminating `swap-inference` instance — CLI trust of the proxy's
MITM CA is the one architectural gap this validation does not cover,
plus the absent-`auth.json` case), (4) image gate, (5) R1 script green.
