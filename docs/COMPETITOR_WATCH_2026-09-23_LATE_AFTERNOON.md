# Competitor watch — 2026-09-23 late afternoon

Pass focus: **C36 vendor verification** — the owed ask from the mid-afternoon
pass (mid-afternoon §3c filed Google Agent Substrate on GKE as corpus-adjacent
new-to-watch, THIRD-PARTY via itbrief.co.uk, "vendor verification owed").

**No full tracked-set re-read this pass.** The mid-afternoon pass re-read all 8
tracked providers on their vendor pages ~14:54–15:12 CDT (8/8 VERIFIED,
NO-CHANGE, zero fetch failures); re-reading them again ~45 minutes later would
be noise, not signal. Tracked-set state: last fully verified 2026-09-23
~15:12 CDT, NO-CHANGE. Vercel Drives GA watch: still beta as of that read
(tenth consecutive no-change pass).

## 1. C36 vendor verification — Google Agent Substrate on GKE

**Source read live this run** (~16:00 CDT, 2026-09-23):
<https://cloud.google.com/blog/products/containers-kubernetes/agent-substrate-available-on-gke>
— Google Cloud's own announcement post, "Agent Substrate available on GKE"
(search metadata dates the post ~Sep 15, 2026 — two days *before* the
itbrief.co.uk piece (~Sep 17) that filed C36).

**Verdict: VENDOR-CONFIRMED.** Every claim the itbrief piece carried is
corroborated on Google's own page:

| itbrief claim (C36 filing) | Vendor page says | Verdict |
|---|---|---|
| Open-source agent-sandbox runtime, offered on GKE | "Agent Substrate is an open-source, secure-by-default agent execution runtime"; "announcing the availability of Agent Substrate on Google Kubernetes Engine (GKE)" | Confirmed |
| Cloud Hypervisor microVMs *or* gVisor | "Hardware-isolated Cloud Hypervisor microVMs or gVisor sandboxes"; "choose between hardware-isolated Cloud Hypervisor microVMs … or gVisor sandboxing" | Confirmed verbatim |
| <500 ms resume | "sub-500ms resume operations"; "In less than 500ms, a sandboxed environment can be resumed to its previous state" | Confirmed verbatim |
| 500+ suspend/resume activations/sec | "over 500 suspend/resume activations per second"; data plane "handles hundreds of suspend/resume operations per second" | Confirmed |
| 1,000+ dormant agents/host | "This zero-idle model can pack over 1,000 dormant agents per host" | Confirmed verbatim |
| Network gateway | "integrated gateway manages all egress and ingress requests"; "egress proxies that enforce granular network policies and inject credentials outside the reach of the agents" | Confirmed (richer than filed) |
| Non-production for all GKE customers; production GA via allowlist | "Agent Substrate is open source and available to all GKE customers for non-production workloads. GA support for production is available via allowlist." | Confirmed verbatim |
| Early design partner Nous Research (Hermes) | "Nous Research has been an early design partner on Agent Substrate" + named customer quote (Hervé Bizira, CBO) | Confirmed (stronger than filed — named quote) |

**New vendor facts not in the third-party filing** (competitive color):

- **10× density headline:** "10x higher density than standard container
  runtimes" — Google's lead number, matching the zero-idle economics.
- **Not GKE-locked:** "available as an open-source solution that runs on any
  Kubernetes infrastructure and is optimized for GKE" — the hyperscaler play
  is open-core portability, not lock-in.
- **Harness-agnostic by design:** "works with any agent framework or harness,
  including Claude Code, OpenClaw, and Hermes" — another datapoint for the
  harness↔compute split (cf. corpus C30).
- **Control/data-plane split:** Kubernetes manages the machines (self-healing
  nodes, autoscaling); a purpose-built data plane does the high-frequency
  suspend/resume directly on local workers — the same execution/machine
  separation shape spark-vm targets with the hosted product.
- **Storage story:** optional Filestore agent volumes (NFS, RWX, POSIX file
  locking) attach/detach in milliseconds — corroborates the itbrief.au
  Filestore-agent-volumes launch (~Sep 19), which names Agent Substrate as a
  supported platform.
- **Price-performance claim:** native Axion support, "up to 30% better
  price-performance for sandbox workloads compared to competitive cloud
  offerings."

## 2. Corpus action

**C36 provenance upgrade: THIRD-PARTY → VENDOR-CONFIRMED** (C30 precedent):
corpus `docs/COMPETITOR_ANALYSIS.md` gains a bottom "Watch update —
2026-09-23 (late-afternoon)" section, and the C36 entry's trailing marker now
reads Vendor-confirmed with a pointer. No new C-number: the filing existed;
only the provenance layer moved. The itbrief.co.uk piece stands as the
discovery source.

## 3. In-lane launches

None new this pass. The C36 item is a vendor confirmation of an existing
filing, not a launch.

## 4. Next pass's asks

- Routine tracked-set re-reads (last full re-read ~15:12 CDT, 2026-09-23).
- Drives GA watch continues (eleventh no-change pass incoming if quiet).
- Watch for the Agent Substrate GitHub repo's public activity (vendor blog
  links the open-source repository) — adoption signal, not a corpus item yet.
