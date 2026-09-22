# C19/C20 corpus consolidation — Brig and Epho

Closes watch items **C19** (Brig) and **C20** (Epho), filed by the
2026-09-22 night watch as pre-window competitors needing "the next
corpus consolidation pass." Surveyed 2026-09-22 ~02:55–03:10 CDT;
read-only, no logins. Raw surveyor captures are in the loop's
`agent_notes/` (workspace-only), not the repo.

Conventions (per the corpus): **VERIFIED** = read on a vendor's own
page, doc, or repo this pass (link inline). **THIRD-PARTY** = reported
by press or third-party sources. **INFERRED** = my characterization,
labeled as such. **UNVERIFIABLE** = no public source exists to check
against.

## 1. Brig (C19) — local microVM containment for coding agents

**What it is.** A Go CLI (`brig`) plus a session daemon (`brigd`) that
runs coding agents inside microVMs **on your own machine** — by NOFire
AI, Apache 2.0, prerelease `0.1.0-rc`
(**VERIFIED**: https://github.com/brig-sh/brig). One command —
`brig run claude ~/code/demo` — starts a sandbox and runs the agent in
it. There is no hosted service, no pricing page, and no multi-tenant
story: Brig is a single-user local containment tool, not a hosted
competitor. Its comparable surface in our tree is the self-hosted /
jail track.

**Substrate (the axis C19 asked for).** macOS 15+ uses the `hvi`
backend of the `hull` runtime; macOS 14 uses `vz`
(`BRIG_HYPERVISOR=vz`); Linux (x86-64/arm64) uses the `urunc` shim
over KVM via nerdctl/containerd; Intel Macs are unsupported
(**VERIFIED**: repo README). On the corpus isolation axis this is
*dedicated kernel per sandbox* — the same boundary tier as E2B's
Firecracker microVMs — but the trust model is **host-vs-agent
containment**, not tenant-vs-tenant. Brig has no tenants; the wall
protects your machine from the agent, not customers from each other.
It does not belong in the multi-tenant rows of the scorecard; it is a
new entry in the local-containment column alongside our jail.

**Profiles.** Eight built in: six `kind: agent` (`claude-code`,
`codex`, `cursor`, `gemini`, `grok`, `opencode`), one `kind: gui`
(`claude-desktop`), one `kind: shell` (`ubuntu`)
(**VERIFIED**:
https://github.com/brig-sh/brig/blob/main/docs/profiles.md). Two
facts worth recording precisely, because third-party coverage blurs
them: (1) `cursor` declares `unpublished: true`, so `brig run`
refuses it before reaching the registry — but the profile's own
`desc:` labels it an "example profile," so the honest read is a
launch-list vs shipped-state mismatch documented in-repo, minor
severity, not a broken launch promise; (2) five of the seven pullable
images are Brig's own multi-arch builds under `ghcr.io/brig-sh`, while
`claude-desktop` (`ghcr.io/nofireai`, aarch64-only) and `ubuntu`
(Docker Hub) sit outside Brig's signature-verification registry, and
Brig warns on every boot of those two.

**Credential handling (relevant to our posture).** The guest boots
with **zero credentials**; credentials reach it only by per-exec
delivery through profile bindings (secret store, env, files).
`brig info` reports binding *names* only, never values — and a test
fails their build if a value ever reaches the output
(**VERIFIED**: docs/profiles.md). There is also a `deny` billing
guard: Brig refuses to forward e.g. `ANTHROPIC_API_KEY` when doing so
would silently move the sandbox off a subscription onto metered API
billing (`BRIG_ALLOW_DENIED=1` is the deliberate override). The
names-only reporting and the billing guard are both bars our own
cred/swapd surfaces should be measured against.

**Egress posture.** The default `shared` network is full internet,
and their README says the quiet part plainly: "anything it can read
it can also send." Egress policy is enforced **only** on hull's `hvi`
backend — and Brig **refuses a policy-bound run on any other backend
rather than run it unenforced**; `shell`/`gui` profiles cannot carry
a policy at all (refused at parse time). That is the fail-closed
downgrade pattern: never silently run a restricted workload on a
substrate that cannot enforce the restriction. Our jail/proxy docs
should state our own downgrade behavior with the same explicitness.
(Image verification, by contrast, defaults to `warn` — it boots
unverifiable images anyway unless `BRIG_VERIFY=require` is set. A
documented tradeoff; ours should say where we stand rather than
implying parity.)

**Strengths.** Best-in-class local DX (brew cask install, `brig
doctor` preflight, profiles as editable YAML with header comments,
XDG discipline, telemetry that counts nothing on Brig's side and is
one command off); the fail-closed policy-downgrade refusal; the
boot-empty credential model with names-only reporting.

**Where spark-vm wins.** Brig answers none of the hosted questions:
no provisioning, no multi-tenant boundary, no approvals plane, no
outside observer (sentinel), no provider abstraction. Our per-VM
tenant + confirmd + swapd-proxy stack is a different product in a
different market — Brig is a complement to our self-hosted track,
not a substitute for the hosted vision.

## 2. Epho (C20) — agents-as-API with multi-provider fallback

**What it is.** A cloud API — `POST /api/v1/chat` with a harness,
model, prompt, provider key, and repos — that spins up a sandbox,
configures the chosen harness (claude / codex / opencode), clones
repos, wires MCP servers, and streams the agent's work back as
server-sent events (async mode with webhooks too). By Bruin Data
Limited, launched ~Sep 7 (**THIRD-PARTY**: Product Hunt launch post,
https://www.producthunt.com/products/epho-claude-code-in-the-cloud;
everydev.ai/tools/epho). This is the task-scoped, session-clocked
shape our hosted thesis explicitly rejects ("a real computer that
stays yours") — which makes its *reliability* engineering, not its
product shape, the thing to learn from.

**Multi-provider fallback (the axis C20 asked for).** The founders'
own words: "Sandbox providers are not very reliable, which means you
need to figure out a multi-provider strategy to avoid failures" —
and Epho "takes care of automatic fallbacks across different
providers" (**THIRD-PARTY**: their Product Hunt post). The primary
source corroborates fallback existence in weaker wording: epho.io
documents that "the run re-queues on a fallback sandbox backend" and
that a durable chat's "conversation outlives the machine it ran on"
via session-snapshot restore (**VERIFIED**). Durable chats restoring
session snapshots on replacement boxes when the underlying box is
gone (**THIRD-PARTY**: everydev.ai). The identities of the
underlying providers are **UNVERIFIABLE** publicly (not named).

Scored against H4's provider-agnostic interface criterion: H4's
`provider_iface` (eight methods — `provision`, `status`, `suspend`,
`dial`, `ssh_info`, `destroy`, `attest_network_isolation`, `snapshot` —
plus the fail-closed `public_ingress` policy flag) with per-shape
capability axes (`supports_suspend`, `memory_resume`,
`wake_reprovisions`) is a *single-provider pluggable adapter*. Epho validates the market need
for the layer **above** the adapter: a failover router that keeps a
session alive across provider failures and restores session
snapshots on replacement boxes. Our interface already gives such a
router its inputs (the capability axes are exactly what a router
needs to pick a fallback target); the router itself is not designed.
Note the honest boundary: `provider_iface` already ships a
`snapshot()` verb, so the missing design is not "snapshots" — it is
the **cross-provider session-state restore contract**: which of the
shipped verbs (`snapshot`/`suspend`/`dial`/`provision`) the router
drives, how a session survives a provider failure when VM-snapshot
restore across providers is not portable, and how the capability
axes pick the fallback target. That is a real H4 follow-up — filed
below.

**Pricing (VERIFIED: https://epho.io).** Per-second, meter runs from
boot to teardown — "nothing idles, nothing is stored, nothing keeps
billing." CPU $0.0000164/vCPU/s, memory $0.0000053/GiB/s, disk
$0.000000036/GiB/s. The default 2 vCPU / 2 GiB / 10 GiB instance is
≈ $0.0000438/s ≈ **$0.158/hour** (computed). Bring your own keys:
model tokens are billed by your provider, never by Epho. $10
starting credit (~60 hours of the default instance). Balance via
`GET /credits`; a turn is refused with 402 at zero.

Pricing comparison (**INFERRED**, with a shape caveat): boat.dev's
published twelve-provider table puts E2B/Daytona/Blaxel at $0.166/h
(first tier) / $0.331/h (second tier). Epho's $0.158/h for 2vCPU/2GiB
lands within ~5% of E2B's first tier — so Epho's differentiator is
**not** raw price. It is the agents-as-API layer (harness
pre-configuration, repo cloning, MCP wiring, event streaming,
async/webhooks) plus the multi-provider fallback. The BYOK shape is
the pricing-thinking data point: infra-only metering with
provider-billed tokens means Epho carries zero model-token margin
risk — worth one line in `docs/PRICING_THINKING.md` next time that
doc is touched.

**Credential handling.** Provider API keys "ride along per-request
and are torn down with the run — Epho never stores them between
turns" (**THIRD-PARTY**: everydev.ai). Contrast with our swapd
posture in one honest line: the secret still transits their API on
every request; ours never lets the operator see it at all. Their
model is better than credential-in-the-sandbox; ours is better than
theirs. Say both.

**Operational shape worth stealing.** Per-second meter with instant
stop — "nothing idles, nothing is stored, nothing keeps billing"
(**VERIFIED**: epho.io); 402-at-zero balance refusal (**VERIFIED**:
epho.io); durable chats with snapshot restore on replacement boxes
(**THIRD-PARTY**: everydev.ai); five active turns with free queueing
(**THIRD-PARTY**: everydev.ai); a plain-HTTP API (no SDK) that drops
straight into GitHub Actions, cron, and chatbots (**THIRD-PARTY**:
everydev.ai). The queue-and-refuse economics are the honest version
of "no session clock" for a task-scoped product (**INFERRED**).

**Where spark-vm wins.** Epho rents task-scoped sandboxes on a
session clock; our thesis is a persistent computer with no clock at
all. Their five-turns-and-queue model is the shape we reject. Our
answer to their reliability lesson is the H4 failover router, not
their product shape.

## 3. Disposition

- **C19 → closed.** Evaluated above: substrate placement (dedicated
  kernel per sandbox, host-vs-agent containment, single-tenant by
  construction), profile/image-verification findings, credential and
  egress posture notes.
- **C20 → closed.** Evaluated above: multi-provider fallback scored
  against the H4 provider-agnostic interface criterion, BYOK
  infra-only pricing, operational shape.
- **New backlog items** (in BACKLOG.md): (a) H4 failover-router
  follow-up — design the provider-failover router + cross-provider
  session-state restore contract on top of `provider_iface`: which of
  the shipped verbs (`snapshot`/`suspend`/`dial`/`provision`) the router
  drives, how a session survives a provider failure when VM-snapshot
  restore across providers is not portable, and how the capability axes
  pick the fallback target (Epho's lesson; the axes are the router's
  inputs); (b) jail/proxy docs state the enforcement-downgrade behavior
  explicitly, fail-closed like Brig's policy-bound refusal; (c)
  `deny`-style billing guard for our cred forwarding — refuse to make
  known metered-billing keys available to a sandbox without an explicit
  override (note Brig's own limit: `deny` guards the environment
  channel only; a `files:` binding can deliver a metered key unchecked,
  deliberately — per docs/profiles.md); (d) PRICING_THINKING.md
  one-liner next touch: Epho's BYOK infra-only metering as a
  pricing-shape data point.
