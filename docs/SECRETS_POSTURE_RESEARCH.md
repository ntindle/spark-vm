# Secrets-posture research: how agent-sandbox vendors handle credentials

**Date:** 2026-09-19. **Archetype:** research (strategy loop).
**Purpose:** corroborate, from each vendor's OWN documentation, the mechanism-level
claims behind the competitor-pass secrets axis, so the R6 security-docs
repositioning can argue mechanism-by-mechanism with links instead of
posture-by-posture from a benchmark. Closes the C3 open-verification items
(E2B allow/deny conflict resolution, E2B accept-before-decide TCP behavior).

**Honest framing (carried from the adoption-research doc):** the secrets-injection
posture is independently re-derived, not a proven lead. This document shows the
pattern is convergent — every serious sandbox vendor has shipped some version of
"the proxy holds the secret, the sandbox doesn't" — and pins down exactly where
swapd's mechanics differ. It is not a "we were first" claim; we make no such claim.

**Verification tags:** `VENDOR-VERIFIED` = exact quote from the vendor's own docs;
`THIRD-PARTY` = claimed only by a non-vendor source; `UNVERIFIED` = not found in
vendor docs. Where a prior claim was only third-party-sourced, this document
records the current status; links are inline per vendor section.

## swapd (this project) — the baseline this doc compares against

Opaque `hsurr:<name>` placeholders; the egress proxy (mitmproxy addon,
`proxy/swap_addon.py`) substitutes real values request-side and scrubs known
secret values back to placeholders in *response* text bodies for allowlisted
hosts (values under 8 chars are never scrubbed; bodies over 5 MB skip swapping
with a durable audit line — finding 71). A TOTP scrub window covers RFC 6238
codes. Every swap and every refusal is appended to the audit log; the audit
write is part of authorization (if the audit line can't be written, the swap is
refused). The agent never sees, and the guest VM never contains, real values.
(Sourced to the repo itself, not to any vendor.)

## The comparison, mechanism by mechanism

| Axis | swapd | E2B | Daytona | Vercel | Cloudflare | Microsandbox |
|---|---|---|---|---|---|---|
| Substitution point | Egress proxy (mitmproxy addon) | Egress proxy | Outbound HTTPS proxy | Sandbox firewall (microVM front) | Outbound handler in Workers runtime | Host-side network stack at the network boundary |
| Placeholder in sandbox | `hsurr:<name>` | `${e2b.identity.tokens.<name>}` (identity tokens) / `Secret.fill` reference | `dtn_secret_<random>` mounted in env var | No placeholder — handler injects into the request itself | None by default — sandbox makes a plain request, handler attaches the credential | `$MSB_<env_var>` (customizable) |
| Does the secret ever enter the sandbox? | No | No ("outside the sandbox when it forwards") | No (env holds placeholder, not value) | Docs imply yes it does not (interception at the boundary); not stated verbatim | No ("secret lives in the Worker's environment and is never passed into the sandbox") | No ("The real value stays in host memory") |
| Injection surface | Request bodies + headers; response scrub | HTTPS **headers only** | HTTPS **headers only** | Request headers/transforms matched by path/method/query/headers | Whatever the handler code does (full programmability) | Headers + Basic-auth decode/substitute/re-encode by default; query/body opt-in; plain-HTTP opt-in |
| Response scrubbing | Yes — real value rewritten to placeholder | Not documented | Yes — "rewrites it back to the placeholder" | Not documented | Not documented (custom handler code could) | Explicitly NOT — "An allowed endpoint that echoes a credential in its response can expose it to the guest" |
| Destination scoping | Per-host allowlists (`hosts.allow` / `ssrf.allow`) | Rule per exact domain or `*.` wildcard; rule alone does NOT grant egress — host must also be in `allowOut` | Per-secret `hosts` (exact + `*.` wildcards; **omitted = unrestricted**) | NetworkPolicy allow/deny | Handler logic + `ctx.containerId` per-instance keys | Allowed-host match + DNS pin + TLS identity + authority alignment (strongest gate of the six) |
| Value storage | Operator-held (swapd users hold their own) | E2B secrets store | Org-scoped, encrypted at rest, never returned by API after creation | Vercel env/secrets | Worker env / Wrangler secrets | Host process memory (+ persisted in host-side sandbox config unless env-referenced) |
| Audit of each injection | Per-decision audit line (durable) | Not documented | Not documented | Not documented | Not documented | Placeholder-block events logged |
| Short-lived / rotated creds | Per-decision; grant TTL clamps | Identity tokens minted fresh per request | Placeholder stable across rotation; new value live within ~15s | Not documented | Handler code's choice | Not documented |

## Per-vendor findings

### E2B — VENDOR-VERIFIED

Doc: https://e2b.dev/docs/network/internet-access ("Per-host request transforms",
"Priority rules", "Behavior of blocked TCP connections").

- Per-host `network.rules` inject headers on outbound requests matching a host;
  `Secret.fill` references are replaced "by the egress proxy ... outside the
  sandbox when it forwards a matching HTTPS request". Identity tokens are even
  stronger: `${e2b.identity.tokens.<name>}` is minted fresh per request, "so the
  token value never passes through your code or the sandbox." Transforms apply
  "to intercepted TLS traffic only, so nothing is injected on plain HTTP."
- **Allow/deny conflict: allow wins** (C3 closed): "When both allow and deny
  rules are specified, **allow rules always take precedence** over deny rules.
  This means if an IP address is in both lists, it will be allowed."
- **Accept-before-decide TCP behavior** (C3 closed): "Due to firewall design,
  blocked connections may appear successful from inside the sandbox. The
  firewall has to accept the connection first before it can decide whether the
  destination is allowed. ... a TCP connection can succeed and report the
  socket as open even when the destination is denied - no packets actually
  reach the destination. To verify that traffic is reaching its destination,
  check for an application-level response ... rather than relying on the TCP
  connection succeeding."
- E2B's two traps, stated in their own words: **opposite conflict resolution to
  Vercel** (allow-wins vs deny-wins) and **phantom-open sockets** — a policy
  ported from one vendor to another without rewriting does not mean the same
  thing.
- Egress grant is separate from transform registration: per the same doc,
  registering a per-host rule "does **not** grant egress on its own" — the
  host must also be in `allowOut`/`allow_out`.

### Vercel — VENDOR-VERIFIED (one item downgraded)

Doc: https://vercel.com/docs/sandbox/sdk-reference (NetworkPolicy class).

- NetworkPolicy `transform` rules inject headers on egress at the firewall,
  outside the microVM; matchers on path, method, query parameters, and headers.
  "Traffic identification is based on SNI (server-name indicator), hence only
  TLS traffic is currently supported." Crucially, TLS interception is
  conditional: "Encryption is not intercepted if no transformation or
  forwarding rules are defined, allowing end-to-end data confidentiality" —
  interception happens *only* when transform/forwarding rules exist. The docs
  imply secrets never enter the sandbox but do not state it verbatim.
- **Deny-wins conflict resolution** (C3's Vercel half confirmed, wording
  corrected): `subnets.deny` — "Those ranges will always take precedence over
  `subnets.allow` and domain-based `allow` entries." The competitor doc's
  phrasing ("Denied ranges take precedence over allowed domains and address
  ranges") is the same substance in non-verbatim words — use Vercel's quote.
- **Plan availability: VENDOR-VERIFIED (re-verified 2026-09-21).** The
  Vercel KB guide [Vercel Sandbox vs E2B](https://vercel.com/kb/guide/vercel-sandbox-vs-e2b)
  (published 2026-03-20, updated 2026-09-04) states verbatim:
  "Credential brokering transformation rules are available on all plans,
  including Hobby." (The SDK-reference page gates transforms on
  "Permissions Required" without naming a plan; the KB guide is the
  authoritative plan statement. This supersedes the 2026-09-19 UNVERIFIED
  reading of the SDK reference page alone.)
- **Default internet access: VENDOR-VERIFIED** (recorded for the swapd-vs-
  `allowOut` comparison): "Every sandbox has outbound access to the internet
  by default. ... By default, internet access is enabled, but you can disable
  it for security-sensitive workloads." Default is allow-all, not deny-all —
  so the transform/egress split is between "default-open egress" and
  "transforms that grant no egress".

### Cloudflare — VENDOR-VERIFIED

Doc: https://developers.cloudflare.com/sandbox/guides/outbound-traffic/.

- Outbound handlers are "programmable egress proxies that run on the same
  machine as the sandbox. They have access to all Workers bindings" — and
  execute "inside the Workers runtime, outside the sandbox." The brokering
  model is explicit: "Because outbound handlers run in the Workers runtime —
  outside the sandbox — they can hold secrets that the sandbox itself never
  sees. The sandbox makes a plain HTTP request, and the handler attaches the
  credential before forwarding it to the upstream service" — with the guarantee
  "**No token is exposed to the sandbox.** The secret lives in the Worker's
  environment and is never passed into the sandbox."
- Per-instance scoping via `ctx.containerId` — "Combine `outboundByHost` with
  `ctx.containerId` to scope credentials or permissions to a specific sandbox
  instance" (example: per-instance key from KV used as injected `x-auth-token`).
- Precedence chain: `deniedHosts` → `allowedHosts` → instance-level
  `setOutboundByHost()` → class `outboundByHost` → `outbound` catch-all.
  Non-HTTP traffic (ports other than 80/443) never routes through handlers.

### Microsandbox (OSS) — VENDOR-VERIFIED

Docs: https://github.com/superradcompany/microsandbox/blob/HEAD/docs/security/secrets.mdx,
`docs/networking/overview.mdx`, `docs/networking/tls.mdx` (superradcompany/microsandbox).

- Mechanism: "Instead of putting a real credential inside the VM, microsandbox
  puts a **placeholder** there. The real value stays in host memory. When the
  guest sends a request to a host you've allowed, the host-side network stack
  swaps the placeholder for the real value at the network boundary, on the way
  out." Injection runs through intercepted TLS: "the host-side proxy decrypts
  the intercepted TLS, verifies the request is really going where it claims,
  substitutes the real value, and forwards it upstream."
- The destination gate is the strongest of the six vendors: allowed-host match
  (TLS SNI vs secret host patterns) **plus DNS pin** ("The destination IP was
  actually resolved for that host through the interceptor, so a hard-coded IP
  with a forged SNI doesn't qualify") **plus TLS identity** (never substituted
  over a connection the host can't see into) **plus authority alignment**
  (request `Host`/`:authority` must match the SNI — "which closes
  domain-fronting"). If the placeholder is detected on an ineligible request,
  the default policy blocks and logs.
- Injection scope: headers + Basic-auth decode/substitute/re-encode by default;
  query params and body are opt-in per secret; plain-HTTP substitution is
  opt-in and "not recommended".
- **No response scrubbing** — documented as an exposed edge, not a gap:
  "The allowed endpoint receives the real credential. This stops exfiltration
  to *other* hosts. It does not stop the host you explicitly allowed from
  misusing what you sent it. … An allowed endpoint that echoes a credential
  in its response can expose it to the guest." This is swapd's and Daytona's
  clearest mechanical edge over Microsandbox.

### Daytona — VENDOR-VERIFIED (re-confirmed 2026-09-19)

Doc: https://www.daytona.io/docs/en/secrets/.

- "Instead of an environment variable holding the actual API key, the sandbox
  holds an opaque placeholder token" (`dtn_secret_<random_string>`); mapping
  is via `secrets={"MY_API_KEY": "my-secret"}` at sandbox create.
- "The proxy substitutes placeholders in HTTPS request headers only. ...
  **Plain HTTP requests** are never substituted. ... **Request bodies**
  (including JSON) are forwarded as-is. ... **URL query parameters** are
  forwarded as-is. ... **Transformed placeholders** are not substituted"
  (Base64-encoded credentials, e.g. Basic-auth helpers, don't match — store
  the pre-encoded value instead).
- Per-secret host allowlist; **omitted = unrestricted** ("the proxy replaces
  the placeholder for requests to any host. Set an allowlist for every secret
  unless you have a specific reason not to").
- Response scrubbing confirmed: "If an upstream response contains the real
  secret value, the proxy rewrites it back to the placeholder before the
  response reaches the sandbox. Code in the sandbox can never read the
  plaintext, even when the destination echoes it back." Daytona even warns
  that echo-service tests are false negatives *because* scrubbing works —
  verify via status codes instead.
- Org-scoped, encrypted at rest, values never returned after creation;
  rotation keeps the placeholder stable with the new value live within ~15s.

### OpenComputer (diggerhq/opencomputer) — VENDOR-VERIFIED

Doc: https://github.com/diggerhq/opencomputer/blob/HEAD/docs/agent-sessions/credentials.mdx
("How your keys are protected"), verified 2026-09-21. Spotted in the
2026-09-21 competitor watch as a lighter docs-verified data point — outside
the five-vendor deep set above.

- "The real key never enters the sandbox. The runtime runs with an opaque
  placeholder, and OpenComputer's **secret-store egress proxy** swaps in the
  real value **in flight** — only on the outbound HTTPS call to the model
  provider (`api.anthropic.com` / `api.openai.com`), enforced by an egress
  allowlist, and nowhere else."
- Their term ("secret-store egress proxy") is the vendor's own, and the
  mechanics match swapd's shape: placeholder in the sandbox, real value
  swapped at the egress boundary onto allowlisted hosts.
- Scope note: documented for model-provider calls; the vendor doc verifies
  the mechanism, not the derivation history — convergence is substantiated by
  the quote, independence of derivation is not claimed here.

## What this means for R6 (the docs repositioning)

The honest, sourced edges swapd can claim — each one vendor-quoted above:

1. **Request-body scope** (vs E2B and Daytona): both substitute HTTPS headers only;
   swapd substitutes into request bodies too. Daytona is the incumbent with the
   fullest version of the pattern — the comparison there is narrow and honest,
   not a posture win.
2. **Response scrubbing** (vs E2B and Microsandbox; **parity** with Daytona):
   Daytona's proxy rewrites echoed real values back to the placeholder just
   like swapd's; E2B does not document scrubbing; Microsandbox explicitly does
   not. The cleanest mechanical contrast here is against Microsandbox, the
   only other OSS entry.
3. **Audited per decision** (vs all five): none of the five vendors document
   per-injection audit lines; swapd's audit write is part of authorization.
4. **DNS pin + authority alignment** (vs swapd, conceded): Microsandbox's
   destination gate is stronger than swapd's per-host allowlists — the docs
   should say so rather than invite the comparison to find it.
5. **Conflict-resolution traps** (steal for the docs): E2B allow-wins and
   Vercel deny-wins in opposite directions, E2B's phantom-open sockets —
   "a policy ported without rewriting doesn't mean the same thing" is a
   docs-worthy operational lesson for anyone self-hosting.

Things R6 must **not** claim: Vercel's "secrets never enter the sandbox" in
vendor's voice (implied, not stated); any first-mover claim (Daytona proves a
major incumbent shipped the full pattern; Microsandbox independently derived
the placeholder variant in the open).

## Open verification (residual)

- Vercel: which plan gates `networkPolicy` transform rules — vendor link not
  found (pricing page is quota-only). Re-check after their docs update.
- Cloudflare: whether response scrubbing is a provided primitive or
  handler-author code — not documented; treat as author code.
- Runloop / Modal: named in the competitor doc's axis table but not deep-read
  here (Runloop "Credential Gateway" is not a name Runloop uses publicly;
  Modal documents `secrets=` env-var injection, not egress-time brokering).
  The R6 docs should cite only the five vendors deep-read in this document,
  plus lighter docs-verified watch-list data points that are explicitly marked
  as outside the deep set (cf. the OpenComputer section above).
