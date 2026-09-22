# Secrets posture: the pattern every sandbox vendor re-derived

**Audience:** operators evaluating spark-vm's credential handling, and
contributors touching the swap path (`proxy/`). For the primary research with
vendor-quoted citations, see [the vendor-quoted research](SECRETS_POSTURE_RESEARCH.md) — this page is
the repositioned summary: what the pattern is, why swapd exists, and exactly
where it differs from the five vendors we read (plus the watch-list data
points below).

**The one honest framing, up front:** the secret-injection posture is
*independently re-derived*, not a proven lead. Daytona — a major incumbent —
ships the full pattern, and Microsandbox independently derived the
placeholder variant in the open. A third convergent data point — spotted in
the competitor watch, outside the five-vendor research set below — is
opencomputer.dev: their docs describe a secret-store egress proxy where the
runtime runs with an opaque placeholder and the real key is swapped
in-flight, only on the outbound HTTPS call to the model provider, under an
egress allowlist ([credentials.mdx](https://github.com/diggerhq/opencomputer/blob/HEAD/docs/agent-sessions/credentials.mdx),
verbatim quote in the research doc, verified 2026-09-21). A fourth —
spotted the same day in the competitor watch — is h-sandbox's Credential
Vault (open-source, self-hosted control plane): their own docs say "the
sandbox sees only fake environment variables or no variables at all" while
"the provider injects the real auth material only for outbound requests
that match the binding" — a fake env placeholder in the sandbox, real value
substituted at the egress sidecar onto host/scheme/method/path-bound
requests (verbatim quote in the research doc, verified 2026-09-21). This document shows
the pattern is convergent: every
serious sandbox vendor has shipped some version of "the
proxy holds the secret, the sandbox doesn't". We make no first-mover claim.

## The pattern

An AI agent's sandbox needs to call authenticated APIs without the sandbox
ever containing the credentials. The convergent answer:

1. The operator holds real values in a store the guest cannot reach.
2. Code in the sandbox carries only an opaque **placeholder** token.
3. A proxy at the egress boundary substitutes the real value into outbound
   requests destined for an allowlisted host — and ideally scrubs it back out
   of the response before it reaches the sandbox.

## How swapd does it

The egress proxy is a mitmproxy addon (`proxy/swap_addon.py`) running as the
dedicated `swapd` user. Code in the sandbox carries `hsurr:<name>`
placeholders. On each outbound request the proxy:

- checks the placeholder against the credential registry,
- injects the real value into **request bodies and headers** for hosts in
  `hosts.allow`,
- scrubs known secret values back to placeholders in response headers and
  text bodies of responses from allowlisted hosts (values under 8 characters are never scrubbed — a
  one-character password would otherwise rewrite ordinary prose; TOTP codes
  are matched as whole tokens; residual stated-not-solved: images and binary
  bodies),
- resolves the destination host **before** the upstream TCP connect, so a
  refused host never even gets a SYN (private ranges, loopback, link-local,
  CGNAT/tailnet space, and the `ssrf.deny` hard list are refused by default;
  the deny list beats the allow list — deny-wins, same direction as Vercel),
- skips swapping for bodies over 5 MB — they pass through with placeholders
  intact — leaving a durable audit note instead of parsing them whole
  (a CPU/memory DoS guard on the addon itself).

The audit write is part of authorization: if the audit line cannot be durably
recorded, the swap is refused. Every swap *and* every refusal is appended to
the audit log; values are never logged. A placeholder seen on an
ineligible request (including inside a base64'd Basic-auth header) is logged
as a warning **and** as a `refused=` audit line — the only signal that a
placeholder went somewhere it should not. The guest VM never contains real
values; the operator holds their own via `cred set`.

## The five vendors, mechanism by mechanism

| Axis | swapd | E2B | Daytona | Vercel | Cloudflare | Microsandbox |
|---|---|---|---|---|---|---|
| Substitution point | Egress proxy (mitmproxy addon) | Egress proxy | Outbound HTTPS proxy | Sandbox firewall (microVM front) | Outbound handler in the Workers runtime | Host-side network stack at the network boundary |
| Placeholder in sandbox | `hsurr:<name>` | `${e2b.identity.tokens.<name>}` (minted fresh per request) / `Secret.fill` reference | `dtn_secret_<random>` mounted in env var | No placeholder — the handler injects into the request itself | None by default — the sandbox makes a plain request, the handler attaches the credential | `$MSB_<env_var>` (customizable) |
| Injection surface | Request headers, bodies, query, and URL path; response scrub | HTTPS **headers only** | HTTPS **headers only** | Request headers via transforms matched by path/method/query/headers | Whatever the handler code does (fully programmable) | Headers + Basic-auth decode/substitute/re-encode by default; query/body opt-in |
| Response scrubbing | Yes — real values rewritten to placeholders | Not documented | Yes — echoed real values rewritten back to the placeholder | Not documented | Not documented (handler code could) | Explicitly **not** — "an allowed endpoint that echoes a credential in its response can expose it to the guest" |
| Destination scoping | Per-host allowlists (`hosts.allow` / `ssrf.allow`); deny list beats allow | Rule per exact domain or `*.` wildcard; rule alone does **not** grant egress — the host must also be in `allowOut` | Per-secret `hosts` allowlist; **omitted = unrestricted** (theirs is opt-out, ours is opt-in) | NetworkPolicy allow/deny; **deny wins** | Handler logic + `ctx.containerId` per-instance keys | Allowed-host match **plus DNS pin** (destination IP must have been resolved for that host through the interceptor) **plus TLS identity plus authority alignment** — the strongest destination gate of the five-vendor deep set |
| Per-decision audit | Every swap and refusal appended to a durable log; the audit write is part of authorization | Not documented | Not documented | Not documented | Not documented | Placeholder-block events logged |

Vendor documentation: [E2B internet access](https://e2b.dev/docs/network/internet-access),
[Daytona secrets](https://www.daytona.io/docs/en/secrets/),
[Vercel Sandbox SDK NetworkPolicy](https://vercel.com/docs/sandbox/sdk-reference),
[Vercel Sandbox vs E2B](https://vercel.com/kb/guide/vercel-sandbox-vs-e2b),
[Cloudflare outbound traffic](https://developers.cloudflare.com/sandbox/guides/outbound-traffic/),
[Microsandbox secrets](https://github.com/superradcompany/microsandbox/blob/HEAD/docs/security/secrets.mdx).

## What swapd can honestly claim

- **Request-body scope** (vs E2B and Daytona): both substitute HTTPS headers
  only; swapd substitutes into request bodies too. Against Daytona — the
  incumbent with the fullest version of the pattern — the comparison is narrow
  and honest, not a posture win.
- **Response scrubbing** (vs E2B, Microsandbox, and h-sandbox; *parity* with Daytona):
  Daytona's proxy rewrites echoed real values back to the placeholder just
  like swapd's; E2B does not document scrubbing; Microsandbox explicitly does
  not; h-sandbox does not document it (their threat model admits a reflecting
  endpoint as a residual risk). The cleanest mechanical contrasts are against
  the open-source entries — Microsandbox, which explicitly does not scrub,
  and h-sandbox, which documents no scrubbing.
- **Audited per decision** (vs all five, and both watch-list data points): none of the five vendors, OpenComputer, or h-sandbox documents per-injection audit lines, and swapd goes one step further — the audit write
  is part of the authorization check, not a post-hoc best effort.
- **Credential-brokering availability** (parity with Vercel): Vercel's own KB
  states transformation rules are "available on all plans, including Hobby"
  ([Vercel Sandbox vs E2B](https://vercel.com/kb/guide/vercel-sandbox-vs-e2b),
  2026-03-20, updated 2026-09-04 — re-verified 2026-09-21; the
  [vendor-quoted research](SECRETS_POSTURE_RESEARCH.md) records the
  verification).

## Where swapd concedes

- **Destination gate strength** (vs Microsandbox): Microsandbox's
  allowed-host match plus DNS pin plus TLS identity plus authority alignment
  closes domain-fronting-class misdirection that swapd's per-host allowlists
  do not fully address. If you harden the swap path, this is the direction.
- **Secret freshness** (vs E2B): E2B's identity tokens are minted fresh per
  request, so the token value "never passes through your code or the
  sandbox"; swapd's placeholders are stable until rotation.
- **TLS interception conditionality** (vs Vercel): Vercel intercepts TLS only
  when transform/forwarding rules exist — end-to-end confidentiality is
  preserved otherwise. swapd, as a transparent egress proxy, sees TLS in
  transit by design; that is the trade the pattern demands, and the operator
  should understand it.

## The conflict-resolution lesson

E2B and Vercel resolve allow/deny conflicts in *opposite* directions —
E2B: allow wins; Vercel: deny wins — and E2B's firewall accepts TCP
*before* deciding, so a blocked destination can report a phantom-open
socket from inside the sandbox (their docs recommend verifying at the
application layer, not the socket). A policy ported from one vendor to
another without rewriting does not mean the same thing. swapd chose
**deny-wins** (the `ssrf.deny` hard list beats `ssrf.allow`) and
**pre-connect refusal** (the destination is resolved and checked before the
upstream SYN), so the failure mode is loud: denied egress fails at connect
time, not mid-handshake.

## swapd vs E2B's `allowOut`: the concrete difference

In E2B, registering a per-host transform rule does **not** grant egress on
its own — the host must also be in `allowOut`. Transform registration and
egress grant are two separate lists. In swapd, the swap decision and the
egress eligibility check are joined at one point of policy:

- swap happens only for hosts in `hosts.allow` (injection eligibility, registry
  binding assumed);
- every host — swap or no swap — must clear the egress guard (private ranges
  refused by default, `ssrf.deny` beats `ssrf.allow`, authority mismatches
  refused) *before* connect (egress eligibility).

Both layers are default-deny where it matters: a fresh install ships
`ssrf.allow` empty, and a missing allow file is itself treated as deny. The
practical difference for an operator: E2B's split lets you register
transforms without opening egress; swapd's join means the injection
allowlist is also where you reason about which destinations may receive
secrets. Plain transit to public hosts still passes through swapd unchanged (in E2B,
transform registration likewise grants no egress — though E2B sandboxes
default to full internet access, not deny-all) — swapd governs *secrets*,
not all egress.

## What this document is not

Not a security certification, not a guarantee of equivalence, and not a
migration guide. The five vendor behaviors above are quoted from their own
docs as of 2026-09-19 (see [the vendor-quoted research](SECRETS_POSTURE_RESEARCH.md) for the
verbatim citations; the Vercel plan-availability item was re-verified
2026-09-21 against the vendor's KB); OpenComputer's egress-proxy note is
verified against its own docs as of 2026-09-21 (verbatim quote in the
research doc), and h-sandbox's Credential Vault note is verified against its
own docs as of 2026-09-21 (verbatim quote in the research doc). Vendor behavior moves, and this page
tracks the release it ships with. When the vendor docs change, update the research doc
first and re-derive this page from it.
