# Competitor watch — C18 resolution: h-sandbox credential vault vs the secrets-posture corpus

Filed by the 2026-09-21 evening watch; **RESOLVED 2026-09-21 ~21:00 CDT**.
Corpus conventions per `docs/COMPETITOR_ANALYSIS.md` § "Corpus conventions":
this doc is a consolidation evaluation, not a time-window survey — no
reach-back beyond the verification below.

## Verdict

**C18 RESOLVED — h-sandbox's Credential Vault is a fourth convergent data
point for the placeholder-swap pattern** (after Daytona, Microsandbox, and
opencomputer.dev). VENDOR-VERIFIED against the project's own docs
(github.com/nabilblk/h-sandbox @ `79d1151`, docs current to 2026-09-14;
read 2026-09-21 ~21:00 CDT).

Their own words, from the Credential Vault security model ("The trusted
path is"):

> 1. A caller sends a secret to Harakiri over an authenticated API request.
> 2. Harakiri validates the host/path/method binding and applies it to the
>    provider-side vault.
> 3. The sandbox sees only fake environment variables or no variables at
>    all.
> 4. The provider injects the real auth material only for outbound requests
>    that match the binding.
> 5. Harakiri stores sanitized metadata and audit events, never the secret
>    value.

That is the pattern exactly: **opaque placeholder in the sandbox, real value
substituted at the egress boundary, destination-scoped** — a convergent data
point from an Apache-2.0 open-source self-hosted control plane rather than a
hosted SaaS.

## Mechanism by mechanism vs the corpus axes

| Axis | h-sandbox (Harakiri) | Notes for the corpus |
|---|---|---|
| Substitution point | OpenSandbox egress sidecar / Credential Proxy (`credentialProxy.enabled`), provider-side | Like swapd's proxy shape, but the substitute is the provider-side sidecar on the request path. Harakiri's product layer disclaims MITM implementation ("Harakiri does not implement ... HTTPS MITM in the MVP"), but upstream OpenSandbox docs describe the sidecar's Credential Vault injection as experimental transparent mitmproxy — so the contrast with swapd is a *layering* difference (swapd owns and operates its intercepting proxy; Harakiri delegates substitution to the runtime provider), not a no-interception claim |
| Placeholder in sandbox | Fake env value (e.g. `OPENAI_API_KEY=fake-openai-key`), or no variables at all | Closest to swapd's `hsurr:<name>` of all the corpus vendors: an explicitly *fake* value |
| Injection surface | Auth material only (bearer / API-key header / basic) for requests matching the binding (hosts, schemes, methods, paths) | Narrower than swapd (which also does bodies/query/path); no body-substitution claim found |
| Response scrubbing | **Not documented** — their threat model admits the residual: "A malicious allowed destination can reflect received credentials in its response" | Same class as Microsandbox's explicit non-scrub; swapd and Daytona stand alone on scrubbing |
| Destination scoping | Exact host (custom profiles) or preset hosts; binding hosts composed into restricted egress policy *before* injection; strict `dns+nft` attestation required (`credentialVaultReady: true`) | Fail-closed posture on enforcement: "Harakiri does not fall back to open outbound access, real environment variables, mounted Secrets, or Kubernetes exec when enforcement is unavailable" — reports unsupported rather than pretending |
| Per-decision audit | Lifecycle audit events, metadata-only, with central redaction before persistence | Per-injection audit not documented (swapd's per-decision-audit claim stands) |
| Custody | Envelope-encrypted workspace custody (per-record DEK, operator-wrapped); ephemeral values never persisted; GitHub App dynamic issuers short-lived, tokens never persisted | Comparable to swapd's `cred` store; the ephemeral-source `requires_reinjection` on resume is the same lifecycle honesty swapd's audit trail aims at |

**INFERRED** — why this matters for the corpus: with h-sandbox the convergent
set now spans hosted SaaS (Daytona), OSS library (Microsandbox), OSS
self-hosted agent computer (opencomputer.dev), and OSS self-hosted control
plane (h-sandbox). Four distinct shapes of "agent sandbox" converged on the
same placeholder-swap pattern (the numbered data points count the
placeholder-swap variant specifically; E2B, Vercel, and Cloudflare were
deep-read for the corpus but are not counted in the convergent set — see the
research doc's mechanism table). The R6 anti-overclaim voice still holds:
convergence is substantiated by the quote; independence of derivation is not
claimed.

## What h-sandbox gets right that the corpus should steal

- **Binding-first injection.** The credential attachment carries a
  host/scheme/method/path binding, and binding hosts are composed into the
  restricted egress policy *before* the credential is applied. swapd's model
  scopes by host allowlist; h-sandbox scopes by host *and* method *and* path —
  a finer grant worth considering for per-entry registry shapes.
- **Refuse-to-degrade as a stated policy.** The Vault path refuses to apply
  when enforcement is unavailable (DNS-only sidecar rejected, no fallback to
  real env vars) rather than degrading silently. swapd's fail-closed
  placements share the philosophy; the corpus should name the behavior.
- **Fake-env-is-placeholder explicitness.** Their docs call the placeholder
  what it is ("fake env") and reject "fake env equal to real material" at
  credential validation (documented in `credential-vault-internals.md`) —
  a cheap guard against placeholder/value collision that
  swapd's placeholder namespace could adopt.

## H4 provider-adapter data

The C18 filing also asked for h-sandbox's OpenSandbox adapter choice as data
for the H4 provider-adapter discussions. Three items, all VENDOR-VERIFIED
from their own docs:

1. **Product/dataplane split.** "Harakiri is a product and control plane on
   top of OpenSandbox. The runtime contract is that OpenSandbox owns sandbox
   lifecycle and sandbox data-plane access; Harakiri owns product state,
   routing records, template metadata, API keys, schedules, usage, and audit
   events." — a clean precedent for spark-vm's control-plane vs provider
   boundary in H4: the adapter is the boundary, not a leaky abstraction.
2. **Adapter discipline.** The `RuntimeProvider` contract maps the public
   attachment contract to any sandbox runtime, but "an adapter is not shipped
   merely because the interface exists. It needs authorization, custody,
   redaction, lifecycle, operator, conformance, threat model, and
   support-matrix evidence." — adapter = contract + evidence, not just an
   interface. H4's adapter surface should adopt the same bar.
3. **One adapter, extension points for the rest.** OpenSandbox is the only
   shipped execution adapter; other runtimes are explicit extension points.
   For H4's boat.dev-first stance, the lesson is to name the
   shipped-vs-extension boundary in the spec rather than implying
   provider-agnosticism.

## Standing items

- **C18**: **CLOSED** — resolved this pass. Fourth convergent data point
  recorded in the secrets-posture research doc; summary doc updated;
  corpus consolidation evaluation complete.
- **C14** (#47 resume-latency target): still **OPEN** — needs a measured
  boat.dev/provider resume baseline; live-API measurement awaits the operator
  per-run spend-cap decision (no movement).
- Carrying forward unchanged: C9 (OpenAI partners), C10 (WSO2 — Sep 29
  webinar is the next trigger), C11 (Baseten–Blaxel integration), C12
  (AgentComputer egress, stronger negative).

---

*Corpus note:* this pass changed corpus records (research-doc vendor
section + summary-doc data-point mentions), per the research-doc-first
convention — the summary doc is re-derived from the research doc, not the
other way around.
