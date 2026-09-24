# Ideal Customer Profiles (ICPs) for spark-vm

Draft — for discussion. These are the three segments spark-vm serves or
plans to serve. Segment boundaries matter for trust/security architecture
decisions (see H11 multi-tenancy audit): segments 1 and 2 demand the
provider-layer root boundary; segment 3 is where a cooperative-jail tier
is acceptable.

## Segment 1 — Self-hosters

Homelab folks who run their own agent's box: Unraid, Proxmox, Hetzner,
or any other cloud VPS. This is spark-vm's origin story — "the tooling
that gives my Muse a bigger VM on Unraid" — and the README carries
copy-paste setup paths for an Ubuntu 24.04 VM on Unraid and for
Hetzner/cloud VPS.

- **Who they are:** technically strong tinkerers; they already run
  infrastructure and treat the agent's box as one more workload.
- **What they expect on trust:** they hold root everywhere; the only
  credential boundary that matters is the secret-proxy one (agent never
  sees real secrets). No provider trust question exists — they are the
  provider.
- **What they need from us:** polished setup docs, per-platform guides
  (Unraid / Proxmox / Hetzner / generic VPS), security hardening notes,
  composable tooling they can adapt. Parity rule applies: features
  should work for them too.

## Segment 2 — Hosted signups

Other Muse owners who want a hosted VM for their agent without running
infrastructure. This is the hosted product the improvement loop is
building toward ("a hosted product other Muses can sign up for").

- **Who they are:** individual developers and AI-assistant power users;
  not infra people, but sophisticated enough to drive a VM.
- **What they expect on trust:** *their* VM. Tenant human holds root
  inside the guest; the operator (us) owns only the provider/hypervisor
  layer and has no normal login inside tenant guests. This is the
  DigitalOcean / Hetzner / Fly.io norm — anything less breaks the
  mental model of buying a VPS.
- **What they need from us:** one-click provisioning on boat.dev (Fly.io
  fallback), live machine control (spark-vm#47), sensible flat pricing,
  and the H11 multi-tenancy audit closed before shared control paths go
  live.

## Segment 3 — Sandbox harness builders (SEPARATE product)

The sandbox project is separate from spark-vm. Its thesis: "open source
code harness sandbox backing for coding agent harnesses" — an open
alternative to E2B/Daytona (Daytona went closed-source June 2026).
Harness integration is per-harness adapters (OrcaReplay-style contract);
concept is flat-rate ~$20/mo sandboxes via suspend-on-idle plus
per-sandbox CPU/memory caps plus egress fencing.

- **Who they are:** teams and builders running coding-agent fleets
  (Claude Code, Muse Code, Codex-class harnesses); they buy sandbox
  capacity, not VMs.
- **What they expect on trust:** tenants are the harness's own agents —
  isolation is about containment and fair scheduling, not adversarial
  privacy. The cooperative-jail tier (operator holds host root, tenants
  get contained guest-root-equivalent) is realistic here *if* stated
  honestly as shared-kernel sandboxing.
- **What they need from us:** density, fast suspend/resume, egress
  fencing, per-harness adapters. Do not conflate this product with
  spark-vm.

## Open validation questions

- [ ] Segment 1: who are the first ~10 real self-hosters beyond the
  author? What platforms are they on? What docs are they missing?
- [ ] Segment 2: what price and feature set makes a hosted signup
  convert? What kills the deal (price? trust? control latency?)?
- [ ] Segment 3: which harness builders have expressed interest? What
  does the adapter contract need to look like for the first harness?
- [ ] Revisit: does the trust-boundary split above still hold after
  real customer conversations?
