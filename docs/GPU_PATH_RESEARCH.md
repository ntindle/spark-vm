# GPU path research

Date: 2026-09-18. Strategy loop, research archetype.

## Why

C6 (competitor pass, `docs/COMPETITOR_ANALYSIS.md`, PR #26) names the GPU
path an explicit criterion for the sandbox-provider decision: which
providers offer GPU shapes, at what price, and whether the provisioning
interface stays provider-agnostic across CPU/GPU shapes. The provider
recommendation (`agent_notes/provider-recommendation-2026-09-18.md`) picked
Fly.io Machines/Sprites for CPU tenants — and Fly removed attached GPUs
("as of 08/01/26" deprecation, effective **July 31, 2026**; confirmed by the
superfly/docs cleanup PR
[#2449](https://github.com/superfly/docs/pull/2449) removing the GPU-enabled
Machines pricing section), so GPU boxes must come from a second provider
behind the same provider-agnostic interface.

The H3 signup design (`docs/HOSTED_SIGNUP_ONBOARDING.md`, PR #24) defines the
interface every provider driver implements: `provision` / `status` / `dial`
/ `ssh_info` / `destroy`, with a `public_ingress: false` network clause.
This pass answers: which GPU providers can sit behind that interface, at
what cost, and what a v1 GPU tier looks like for both the hosted product
and self-hosters.

## Evaluation axes

1. **GPU shapes** — which cards / memory classes.
2. **Price** — on-demand $/GPU-hour for a representative shape; any flat
   floors or commitments.
3. **Provisioning API** — programmatic create/destroy/start/stop.
4. **SSH** — real SSH into the box (agent workloads need a shell).
5. **Persistence** — stop/suspend with disk persisted, resume; snapshot story.
6. **Interface fit** — can `provision`/`status`/`dial`/`ssh_info`/`destroy`
   map cleanly?

## Headline numbers (surveyed 2026-09-18)

Representative on-demand GPU $/hr:

| Provider | A100 40GB | A100 80GB | H100 80GB | Billing notes |
|---|---|---|---|---|
| Northflank | $1.42 | $1.76 | $2.74 | per-second; CPU+RAM+storage bundled |
| RunPod (Secure Cloud) | — | ~$2.04–2.50 | ~$2.89–3.49 (PCIe) | per-second; Community ~30–40% cheaper |
| Lambda Labs | $1.29 | $1.79 | $2.99 | per-minute |
| Modal | $2.10 | $2.50 | $3.95 | per-second; base = preemptible, 3x reserved |
| Daytona | — | — | $2.27 (preemptible) | per-second; GPU **ephemeral-only** |
| Vast.ai (marketplace) | ~$0.50–0.80 | ~$0.60–0.80 | from ~$1.77 | host-set, dynamic |

E2B has no public GPU tier (BYOC only), so the C6 "E2B and we don't"
framing holds. Flat floors: none verified anywhere — Modal $30/mo and
Daytona $200 credits are giveaways, not floors; RunPod/Vast.ai minimum
balances (~$5) are commonly cited but unverified.

## Provider notes

### RunPod — best default fit

- **Shapes:** RTX 3090/4090, A40/L40/A4000/A5000, L40S, A100 40/80GB
  (PCIe/SXM), H100 (PCIe/SXM), H200, B200. Two tiers: **Secure Cloud**
  (datacenter, SOC2) and **Community Cloud** (peer-hosted, cheaper —
  untrusted third-party hosts, wrong trust story for tenants).
- **Price (mid-2026 surveys of runpod.io/pricing):** Secure — RTX 4090
  $0.69/hr, A100 80GB $2.04–2.50/hr, H100 $2.89–3.49/hr (PCIe);
  per-second billing.
- **Provisioning API:** `runpodctl` CLI (create/list/start/stop/remove,
  ssh-info) + REST (`POST /pods`, `GET /pods/{podId}`,
  `POST /pods/{podId}/stop`, `DELETE /pods/{podId}`) + Python SDK +
  MCP tools — the closest 1:1 map to
  `provision`/`status`/`dial`/`ssh_info`/`destroy` of the group.
- **SSH:** yes — each pod exposes an SSH port; standard
  `ssh -p <port> root@<pod-ip>` plus key upload.
- **Persistence:** network volumes ($0.07–0.10/GB-month) persist across
  pod deletion and re-attach to new pods. **Billing nuance the interface
  layer must encode:** stopping a pod does NOT stop GPU billing
  entirely — stopped pods bill a reduced disk rate (~$0.10–0.20/hr);
  only **terminate** ends billing, and terminate keeps only the network
  volume. A naive "stop = free" model would bleed money.

### Northflank — best managed-platform alternative

- **Shapes:** 18+ GPU types (A100 40/80GB, H100, H200, B200, L4, L40S,
  MI300X, RTX Pro 6000 Blackwell, GB300, TPU Ironwood) + time-slicing/MIG.
- **Price (Northflank's own blog/pricing, 2026):** L4 $0.80 / A100-40
  $1.42 / A100-80 $1.76 / H100 $2.74 / H200 $3.14 — **all-inclusive**
  (CPU, memory, storage bundled), per-second, pay-as-you-go, no seats.
- **SSH:** documented — SSH identities (team-level, own keys),
  `northflank ssh service`, `--proxyOnly` for plain ssh/sftp/rsync/scp.
- **Persistence:** stateful services with per-replica persistent volumes,
  pause/resume, snapshots; microVM isolation (Kata/Firecracker/gVisor).
- **Caveats:** platform-shaped (services/jobs), not bare VMs — the driver
  maps tenant → stateful service + volume, which is workable but less
  1:1. One blog post frames GPU access as "request GPU access" — gating
  for small accounts needs verification during onboarding.

### Lambda Labs — training/batch overflow

- **Shapes:** B200, H100, GH200, A100, A10, A6000, V100.
- **Price (Northflank's 2026 tracking of Lambda's published rates):**
  A100-40 $1.29 / A100-80 $1.79 / H100 $2.99 per hour, pay-per-minute,
  no egress fees.
- **SSH:** yes — full `ssh ubuntu@<IP>`, key required at launch. Simple
  REST API (launch/terminate, key management).
- **Persistence: no stop/resume.** Billing stops only at terminate, which
  wipes `/home/ubuntu`; persistence lives on separate filesystems
  mounted at `/lambda/nfs/<name>`. Launches take 3–15 min and on-demand
  GPU availability is frequently sold out.
- **Fit:** weak primary for *persistent* tenant computers; good as a
  batch/training overflow tier.

### Modal — fails SSH and persistence

- **Shapes/prices:** the widest managed menu (T4 $0.59 → B200 $6.25/hr;
  verified against modal.com/pricing via three independent third-party
  rate tables). Per-second, base = preemptible, non-preemptible 3x.
- **Fail conditions:** no documented real SSH (SDK exec only), no
  suspend/resume (containers ephemeral, max 24h; state must live on
  Modal Volumes). It's a serverless compute product, not a VM product —
  the wrong shape for a persistent agent computer, however good the
  rate card is.

### Daytona — fails persistence for GPU

- **GPU:** H100 $2.27/hr preemptible (daytona.io/pricing, read today),
  plus H200/B200/RTX Pro 6000/RTX 4090/5090 — **but GPUs are
  experimental** (support must grant access) and, crucially, **GPU
  sandboxes are ephemeral only**: the stop/archive/pause/fork lifecycle
  that makes Daytona attractive on CPU does not apply to GPU. Fails the
  persistent-tenant-computer requirement outright.

### Vast.ai — budget overflow tier

- **Marketplace** (host-set prices): A100 80GB ~$0.60–0.80/hr, H100 from
  ~$1.77/hr. SSH yes, stop/start preserves the container filesystem,
  stopped instances bill storage-only (~$0.03/GB-mo).
- **Cost:** marketplace reliability variance (hosts vanish, spot
  interrupts), inconsistent API, defensive polling needed. Cheapest +
  SSH + stop/resume make it the natural *cheap tier*, never the default.

### Akash — fails operational overhead

- Auction-priced GPUs, but: **crypto payments** (AKT/USDC escrow on-chain),
  no native SSH, persistence provider-dependent, deployment-shaped not
  VM-shaped. Too much operational load for a small operator.

## Recommendation (research findings — operator decides)

1. **RunPod (Secure Cloud)** as the default GPU driver target: real SSH,
   VM-like pods, persistent network volumes, full create/stop/destroy/
   ssh-info API + CLI, widest reputable GPU menu, no commitments,
   cheapest credible on-demand rates. Encode the stop-vs-terminate
   billing nuance in the interface layer.
2. **Northflank** as the managed-platform alternative: documented SSH,
   REST/CLI, stateful volumes, per-second all-inclusive billing; verify
   GPU-access gating for small accounts during onboarding.
3. **Vast.ai** as a budget overflow tier; **Lambda Labs** for
   batch/training overflow. **Daytona and Modal fail the persistence
   requirement; Akash fails operational overhead.**

## Interface design note (for H4)

The provider-agnostic interface from the H3 design keeps working across
CPU/GPU shapes if the `provision` request gains a shape descriptor
(suggested: `gpu: true|false`,
`gpu_class: "L4"|"A100-40"|"A100-80"|"H100"`, plus `preemptible: bool`
for providers like Modal that price tiers differently). GPU drivers are
*second* drivers, not a second interface — the tenant lifecycle
(create → suspend → wake → destroy) is identical; only the shape
selection and cost accounting differ.

## v1 GPU tier shape (proposal, not commitment)

- **Who it's for:** tenants doing local model work (fine-tuning,
  inference dev, video/media pipelines) — the agent's day-to-day still
  runs CPU.
- **Shape:** A100-40 or L4 as the entry GPU tier (cheap enough to keep
  idle-suspend economics sane); H100/H200 for explicit paid demand.
- **Billing:** billed only while running; the suspend-on-idle story
  applies to GPU boxes exactly as to CPU boxes — a suspended GPU box
  must cost storage-only, or the tier is a billing trap. Northflank's
  all-inclusive rate makes this math simple; RunPod needs the
  stop-vs-terminate distinction encoded.
- **Honesty rule** (from PRICING_THINKING.md + POSITIONING.md
  anti-claims): no GPU tier is announced, priced, or marketed until a
  driver exists against a real provider. This doc is research, not a
  launch commitment.

## Open verifications (later turns; nothing blocked)

- RunPod / Vast.ai minimum deposit amounts (commonly cited ~$5, unverified).
- Northflank GPU-access gating for new/small accounts.
- Whether Northflank GPU workloads support true suspend-to-disk + wake
  (determines whether the idle tier R4/C5 extends to GPU).
- Daytona on-demand (non-preemptible) GPU rates; Lambda persistent-FS
  $/GB-mo; Akash current market H100 rates.

## Sources

Surveyed 2026-09-18 (links inline). Primary: modal.com/pricing (via
three independent third-party rate tables, 2026-06/07);
northflank.com blog + pricing page; daytona.io/pricing + docs (read
2026-09-18); runpod.io/pricing + docs (via 2026-07-17 third-party
factsheet); superfly/docs#2449 (Fly GPU deprecation); community.fly.io
GPU deprecation thread (Feb 2026). Working notes:
`agent_notes/gpu-provider-findings-2026-09-18.md`.

## Follow-ups

- **H4** (provisioning automation): add `gpu` + `gpu_class` (+
  `preemptible`) to the shape descriptor when the driver layer lands;
  encode RunPod's stop-vs-terminate billing distinction.
- **C6** (competitor pass): this doc is the deliverable — close C6 with
  a link to it.
- **PRICING_THINKING.md** (PR #30): GPU boxes are a separate cost basis
  — per-box packaging applies per tier, and the no-free-tier abuse
  calculus (card-on-file) applies doubly to GPU.
