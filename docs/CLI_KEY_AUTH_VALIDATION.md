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
(`muse-build/1.3.0`, non-interactive):

1. A stub HTTP server on `127.0.0.1:37661` recorded every request's
   method, path, and headers, and answered 400 to everything.
2. Ran, with all proxy env vars unset (no MITM in the loop):
   `META_API_KEY=hsurr:test-placeholder timeout 25 muse exec --provider
   meta --base-url http://127.0.0.1:37661 --reasoning-effort minimal "ping"`
   (`hsurr:test-placeholder` is a placeholder string, not a real secret;
   the stub never contacted the real provider).
3. Killed the CLI after capture, inspected the request log, removed the
   stub and its directory from the box. No box state was mutated
   (`~/.config/muse/auth.json` untouched; `muse auth set` was deliberately
   not exercised — it writes the user's credential store).

## Findings

- **F1 — The CLI accepts static API keys, three ways** (help text, verified
  2026-09-19): `META_API_KEY` environment variable — `muse login --help`
  states *"META_API_KEY always takes priority over the account login"*;
  `muse auth set --provider meta --api-key-stdin` (stdin-only, never
  argv/shell history); `muse exec --api-key-stdin` (per-run key from
  stdin). The provider set is currently just `meta` (the only
  `--provider` value accepted), which is the provider the tenant path
  needs.
- **F2 — The key is sent as `Authorization: Bearer <key>` on every
  inference request.** All 12 captured requests carried
  `Authorization: Bearer hsurr:test-placeholder` (12/12, both request
  shapes the CLI makes: `GET /muse-code/models` and
  `POST /responses`). The placeholder arrived byte-identical — the CLI
  does not munge, quote, or case-fold it.
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
- **F5 — No OAuth credential is needed on the tenant box.** With
  `META_API_KEY` set, the CLI made its requests without consulting
  `auth.json` (the login priority rule is documented, and no browser
  code-approval flow was triggered). The tenant image therefore never
  needs `~/.config/muse/auth.json` to exist at all.

## Tenant-shape recommendation for the R2 feature run

Prefer provision-time `META_API_KEY=hsurr:llm-api` in the tenant's
environment over `muse auth set` in the image:

- Env injection happens at provision time (H4 interface), so the golden
  image carries no auth-store file at all — consistent with the R2
  image-bake rule ("bake placeholders, never values") and trivially
  rotatable per tenant.
- `muse auth set` writes a credential file under `~/.config/muse/`;
  snapshotting or copying that home directory (H13 suspend/wake, image
  capture) would carry the placeholder file around — harmless (it's a
  placeholder) but a needless second credential-shaped surface to audit.

## What this did NOT prove (kept open, non-blocking)

- The full round trip through the real `swap-inference` mitmproxy
  (placeholder in → real key out on egress). The swap side is covered by
  the proxy's own tests (`proxy/test_swap_addon.py`,
  `test_bug_inference_mode_header_only`); the client half is what this
  experiment adds.
- TLS-terminated routing (the experiment used `http://`); the inference
  proxy MITMs TLS, which is unchanged client behavior.
- Other subcommands (`muse mcp login` is OAuth — a separate flow,
  irrelevant to inference auth).

## Decision record

`PRE_SEEDED_HARNESS_RESEARCH.md` §6.2's highest-risk unknown is resolved:
**the Muse CLI supports static-key auth and emits exactly the
`Authorization: Bearer <placeholder>` wire format the inference proxy's
`bearer_header` placement swaps.** The R2 feature run's validate-first
gate is lifted — proceed to (1) golden-image manifest, (2) injector,
(3) `<harness-auth-probe>` per §5, (4) image gate, (5) R1 script green.
