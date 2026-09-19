# Org-policy research (H16)

**Status:** research. The design/implementation of the org-policy layer is
H16; this doc is its research half and design input.
**Feeds:** H16 (org-policy layer), H9 (tenant identity — policy needs a
principal), H10 (per-tenant approvals — approval policy is one axis),
H11 (multi-tenancy audit — audit is another axis).
**Feeding off:** competitor watch #82 (GitHub enterprise-managed sandbox
policies), #81 (secrets-posture vendor corroboration — one open item
resolved here).

## 1. The question

H16 says the hosted product needs an org-policy layer so the pitch works
for enterprises, not just solo developers: per-agent filesystem/network
rules plus audit. The open question this doc answers: **what do org-level
policies for agent VMs/sandboxes actually look like across the market,
mechanism by mechanism — and what would spark-vm have to build to be
credible on that axis?**

Confidence labels: `[V]` = vendor's own docs; `[3P]` = third-party
characterization (treat as lead, not fact).

## 2. What the market does

### GitHub Copilot — enterprise-managed sandbox policies [V]

Enterprise-managed sandbox policies for Copilot in JetBrains IDEs, public
preview September 8, 2026 —
[GitHub changelog](https://github.blog/changelog/2026-09-08-enterprise-managed-sandbox-in-copilot-for-jetbrains/):

- **Scope (six controls):** sandbox enablement, filesystem access, network
  access, proxy settings, developer-tool access, macOS Keychain access
  ("and more").
- **Precedence:** "Managed restrictions take precedence over user settings.
  Copilot locks affected controls in the IDE and identifies settings managed
  by your organization." Managed settings render as "(managed)" in the IDE
  and cannot be relaxed locally — the effective policy is the intersection
  of the managed ceiling and any narrower local choice.
- **Attestation:** "enterprise policy diagnostics to verify that policies
  are correctly detected and enforced on your device" — policy *presence*
  is reported, not just assumed.
- Settings surface appears only when the org enables the Editor Preview
  feature flag or configures a managed setting.

This is the enterprise reference design: centrally governed, override-proof
at the endpoint, with detection + enforcement diagnostics.

### Vercel Sandbox — credential brokering + runtime network firewall [V]

[Vercel KB](https://vercel.com/kb/guide/vercel-sandbox-vs-e2b) (published
2026-03-20, updated 2026-09-04), verbatim vendor claims:

- **Credential brokering:** "A proxy sits outside the sandbox security
  boundary and intercepts outbound requests. When the sandbox code calls an
  API endpoint without authentication headers, the proxy injects credentials
  into the HTTP headers in transit. If the sandbox code tries to set the
  same headers (to redirect authenticated requests to an attacker-controlled
  endpoint), the proxy overwrites them." **"Credential brokering
  transformation rules are available on all plans, including Hobby."**
  - ⚠️ Resolves an open verification item: the R6 notes (PR #81) had
    downgraded "Vercel brokering on every plan" to third-party/unverified
    because vendor docs didn't state it. Vercel's own KB now states it
    explicitly — treat as vendor-verified for Vercel Sandbox's brokering.
- **Network firewall:** three modes — `allow-all` (default), `deny-all`
  (blocks everything including DNS), and user-defined domain+CIDR rules.
  Domain matching via SNI; CIDR rules for IP-range and non-TLS traffic.
  "Policies update at runtime through `updateNetworkPolicy()` without
  restarting running processes."
- **Conflict resolution:** "Denied ranges always take precedence over
  allowed ranges and domain-based rules."
- **On E2B [3P]:** "E2B also provides network controls through domain allow
  lists and IP/CIDR allow/deny lists, with the opposite precedence model:
  allow rules take precedence over deny rules. E2B supports domain matching
  in allow lists only (not deny lists), using Host header inspection on
  HTTP/80 and SNI on TLS/443." — Vercel's characterization of a
  competitor; E2B-side vendor verification still outstanding (was open in
  #81, remains open).

### Daytona — org tiers gate policy, audit logs [V platform + 3P policy]

- Platform layer [V] (Daytona GitHub README): Organizations, API Keys,
  Limits, Billing, **Audit logs**, OpenTelemetry, Integrations, "Security
  exhibit"; system tools include Webhooks and **Network limits**.
- Org-tier gating [3P] (skill notes, Sep 2026): Tier 1/2 orgs are
  restricted to an essential-services whitelist (npm, PyPI, apt, GitHub,
  major AI APIs, common CDNs) with no arbitrary-egress override;
  arbitrary egress requires Tier 3+. Runtime policy overrides are gated to
  org tier + permissions.
- Network limits [3P]: deny-all plus domain/CIDR allow lists; updatable on
  a running sandbox (docs: `daytona.io/docs/en/network-limits/`).

### Runloop — policy as an API resource [V SDK + 3P enterprise]

- `runloop.networkPolicy` (create/list/update egress rules) and
  `runloop.gatewayConfig` (API proxy configurations) are first-class SDK
  resources — policy is managed like any other resource, runtime-updatable.
- Blueprints standardize environments across teams (org-level consistency
  via image, not per-box config).
- Enterprise [3P]: SOC2, "Deploy to VPC" (infrastructure inside the
  customer's AWS VPC — policy enforcement under customer network control).

### Upstash Box — per-box policy + Attach Headers [3P]

[Upstash blog comparison](https://github.com/upstash/upstash-web/blob/HEAD/data/blog/2026-06-18-upstash-box-vs-daytona.mdx)
(Upstash-authored; Daytona characterizations treated as third-party):

- Per-box network policy: `allow-all` (default) / `deny-all` / custom
  allowlist by domain/wildcard/CIDR; **private IPs always blocked**, even on
  allow-all.
- "Attach Headers": host-side secret injection into outbound requests —
  same class as Vercel brokering and spark-vm's swapd.
- Billing: $0.10 per *active* core-hour, memory free; free tier (10
  concurrent, 5 CPU-hrs/mo, $1 LLM budget). Active-CPU pricing is the
  emerging price anchor (Vercel: $0.128/vCPU-hr active).

### OSS structural analogs

- **mattolson/agent-sandbox** (OSS): policy YAML for domain allowlists;
  mitmproxy sidecar with `PROXY_MODE=log` (observe-before-enforce — the
  logging mode shows what endpoints agents need before policy hardens),
  structured JSON logs, **two-layer enforcement** (proxy allowlist +
  iptables to prevent bypass), SSH blocked / git-over-HTTPS only. Its m15
  milestone adds proxy-side secret injection: host-owned secret dir
  (`0700`, files `0600`), mounted read-only **into the proxy only**, never
  the agent container, `basic`/`bearer` header transforms, logical secret
  IDs in policy. This is an independent re-derivation of swapd's
  placeholder-swap design — quotable corroboration for R6.
- **abraxarion/agent-box** (OSS, Bubblewrap): honestly states its floor —
  "Not secret isolation. Host-readable secrets remain readable" and
  "Network is all or nothing." The tier below which policy doesn't exist;
  spark-vm's policy layer competes above this.

## 3. The mechanism table

| Axis | GitHub Copilot | Vercel Sandbox | Daytona | Runloop | Upstash Box | spark-vm today |
|---|---|---|---|---|---|---|
| Org-level policy | ✅ managed policies, IDE-locked | org tiers (via plan) | ✅ org tiers gate overrides | ✅ networkPolicy API | per-box only | ❌ none |
| FS access rules | ✅ managed FS access | VM boundary | sandbox boundary | sandbox boundary | sandbox boundary | VM boundary (no policy) |
| Network rules | ✅ managed net access | ✅ domain+CIDR, deny-precedence, runtime-updatable | ✅ deny-all + allow lists, tier-gated | ✅ networkPolicy resource | ✅ domain/wildcard/CIDR, private-IPs-always-blocked | ✅ ssrf.allow/ssrf.deny + deny file (single-tenant) |
| Secret handling | ✅ managed Keychain access | ✅ brokered outside boundary (all plans) | env inside sandbox [3P] | gateway config | ✅ Attach Headers | ✅ swapd placeholder-swap |
| Audit / attestation | ✅ enterprise policy diagnostics | SOC2 infra | ✅ audit logs, OpenTelemetry | SOC2 | — | audit log (single-tenant, confirmd) |
| Policy as code/API | — | ✅ updateNetworkPolicy() | ✅ limits API [V platform] | ✅ SDK resource | — | ❌ config files only |
| User-override-proof | ✅ "(managed)" locks | — | ✅ tier-gated overrides | — | — | n/a (single user) |

## 4. Recommendations for H16

Table-stakes axes (the market has converged; H16 should implement all six):

1. **Org policy object**: per-tenant/org policy with fs-access, network,
   proxy, dev-tool, and secret-scope axes (GitHub's six controls are the
   vocabulary). Stored host-side, never agent-writable (cf. mattolson's
   "the agent container must not be able to read or replace its own
   secrets" rule; our H11 audit precedes any shared path — MEMORY).
2. **Precedence rule**: managed policy beats per-agent/per-user settings,
   deny beats allow on conflicts (Vercel's rule, not E2B's inversion).
   spark-vm's `ssrf.deny` already follows deny-precedence — the org layer
   extends that, not invents it.
3. **Policy as a resource**: API-managed (Runloop/Vercel pattern),
   runtime-updatable without restarting agents.
4. **Diagnostics**: an agent-visible "what policy applies to me" endpoint —
   GitHub's enterprise policy diagnostics, but readable by the Muse itself
   so a denied action is debuggable (nobody in the market does this for the
   agent's own debugging; it's a differentiator).
5. **Audit**: every policy evaluation logged to the per-tenant audit log
   (feeds H11).
6. **Observation-before-enforcement**: a log-only policy mode (mattolson's
   `PROXY_MODE=log`) so orgs see what their agents actually need before
   hardening — de-risks adoption.

Nobody-cover gaps (differentiators, not table stakes):
- Policy simulation/dry-run ("what would this break?") before enforcing.
- Agent-visible denial reasons (the Muse asks "why was this blocked?" and
  gets the matching rule, not a dead end).
- Federated policy for BYO-infra (tailnet-shaped) deployments — GitHub's
  model assumes managed endpoints; spark-vm's self-hosted path needs policy
  that travels with the box, not the dashboard.

Sequencing: H9 (tenant identity) first — policy needs a principal; then
H16's policy object + diagnostics; H10's approval policy and H11's audit
ride on the same per-tenant substrate.

## 5. Limitations

- Daytona's and E2B's own docs on tier-gating and conflict resolution were
  not read this pass; the third-party characterizations are leads, not
  facts. E2B-side allow-precedence remains unverified in E2B's own docs
  (carried over from #81).
- GitHub's policies are IDE-endpoint policies (local agents), not
  cloud-sandbox policies — the transfer to hosted VMs is an analogy, not a
  1:1 port.
- Pricing details (Upstash, Vercel) were collected for the positioning
  axis and are point-in-time.
