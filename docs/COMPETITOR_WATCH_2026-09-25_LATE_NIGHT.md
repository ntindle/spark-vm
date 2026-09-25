# Competitor watch — 2026-09-25 (late night)

Lead-resolution pass against the 2026-09-25 post-post-late-evening
pass (`docs/COMPETITOR_WATCH_2026-09-25_POST_POST_LATE_EVENING.md`).
Survey window **2026-09-25 ~17:54–18:30 CDT** — read-only fetches and
searches; no logins, no writes. Scope note: this pass deliberately did
NOT re-survey the full tracked set — it was **9/9 VERIFIED NO-CHANGE**
~35–50 minutes earlier (post-late-evening window ~16:24–17:05, and the
17:25–17:45 lead-resolution pass retired C56/C52) — so a re-read adds
nothing; the value this slot is in re-verifying the carried leads live
and running a delta-only news scan.

Evidence labels: **VERIFIED** = read on a vendor's own page, doc, or
repo this run. **VENDOR-VERIFIED** = confirmed on the vendor's own
page, docs, or changelog read this run (full page, not snippet).
**THIRD-PARTY** = press/third-party. **snippet-level** = seen only
via search snippet. **UNVERIFIED** = a public page exists but could
not be fetched this run (never reported as NO-CHANGE). **VERIFIED
absent** = the vendor's own page was read this run and the item is
confirmed not present on it.

Surveyor captures live in the loop's `agent_notes/` workspace
(`surveyor-a-20260925-1754.md`, `surveyor-b-20260925-1754.md`), not
the repo.

## 1. Carried leads — all re-verified live, all carried again

### C37 — Freestyle Pro fee (CARRY, VENDOR-VERIFIED NO-CHANGE)

`freestyle.sh/pricing` re-fetched live this run (full page, 78 lines).
The Pro plan's monthly dollar amount is **still not printed** — the
only dollar figure on the page is the $50 Hobby reference ("$50 on
Hobby covers your first $50 of usage"; "your monthly fee is a
commitment that doubles as usage credit on top of that: you pay the
greater of your plan fee or your usage"). Rate card verbatim and
unchanged: vCPU $0.04032/h (200/mo included), GiB memory $0.0129/h
(400/mo), GiB storage $0.000086/h (60,000/mo), data transfer $0.02/GB
(50 GB free / 500 GB paid). The Pro plan appears only in the limits
comparison table (Concurrent VMs 400, Saved VMs 4,000, Snapshots
12,000, Total vCPUs 16,000, Total Memory 32,000 GiB, Total Disk
62,500 GiB, Data Transfer 500 GB/mo; Persistent Snapshots ✓;
Persistent VMs ✓; Custom Sizing ✓; max 32 vCPU / 64 GiB / 256 GiB
per VM) with no fee attached. Page-structure delta vs prior passes:
the page has grown — full Free/Hobby/Pro limits table, expanded FAQ
("What happens if I exceed my plan limits?", "Can I switch plans at
any time?", "Do you offer custom enterprise pricing?") — but no Pro
fee added. The carry stands: Pro fee is structurally omitted from
public pricing; a signed-in dashboard check remains the only
unexercised path.

### C26(a) — DO snapshot-rate 10× conflict (CARRY, VENDOR-VERIFIED both sides)

Docs pricing page re-read live
(`docs.digitalocean.com/products/managed-agents/agent-harness-runtime/details/pricing/`):
still "Last verified 22 Sep 2026" (not re-stamped); "Billed per GiB
stored when you use snapshots or checkpoints at **$0.05 per
GiB-month**" — verbatim, unchanged; sibling lines (Session Storage
(Volumes), BYOT custom templates) also $0.05/GiB-month, unchanged.
DO's own launch blog (read live this run, `digitalocean.com/blog/why-we-built-managed-agents`)
agrees: "snapshots at $0.05 per GiB-month". The press-release side is
unchanged too: syndicated BusinessWire copies still state "$0.005
per GiB-month". The intra-vendor discrepancy (docs+blog vs press
release) persists — neither side corrected. Note for the corpus: the
$0.005 figure appears ONLY in the press release; every vendor-owned
surface agrees on $0.05, and DO's standing general-product snapshot
pricing is $0.05/GB-month.

### C26(b) — DO active-CPU billing timing conflict (CARRY, VENDOR-VERIFIED)

Same docs page, read live this run. The footnote is still verbatim:
"*Active CPU billing is coming soon. Until then, you will be billed
at 25% of the vCPUs allocated to your sandbox. Paused sessions incur
no compute charges.*" — and it still contradicts the body copy,
also verbatim: "Each session is billed per second of active compute
based on actual CPU consumption** and peak memory usage" and "When
an agent is waiting and consuming no CPU, its CPU charge falls to
zero." The vendor launch blog (read live this run) still presents it
present-tense: "DigitalOcean bills CPU per second of actual use at
$0.044 per vCPU-hour" — agreeing with the body copy, not the
footnote. Active-CPU billing has NOT shipped per the docs. Timing
conflict unresolved.

### C54 — Perplexity "Escaping SPACE: Part I" primary body (CARRY, still UNVERIFIED-blocked)

The primary article body remains unreadable through every legitimate
public path attempted this run: direct URL
(`https://www.perplexity.ai/hub/blog/escaping-space-part-i`) 403s as
on all prior passes; the web.archive.org availability API confirms a
snapshot exists (20260924213405) but its recorded status is **204
(empty capture)** and fetching it returned an empty body / upstream
500 after retries — a dead end; `r.jina.ai` text-extraction proxy is
blocked by browser policy; the blog index loads but carries only the
one-line listing ("Sep 23, 2026 — Escaping SPACE: Part I —
Red-teaming VM isolation and network confinement for AI agents"); no
full-text mirror found in search. Never claimed as NO-CHANGE —
simply inaccessible.

**Corpus enrichment (THIRD-PARTY, delta vs the filed stats):** the
second dennysentinel.com analysis (2026-09-24, "The Kernel Held. The
Allowlist Didn't.") was read beyond the bare numbers this pass.
Beyond the corpus stats (216 runs, 0/108 VM escapes, egress
allowlist bypassed in 11/54 partial-network runs), the analysis adds:
models tested — Claude Opus 5.0, DeepSeek V4 Pro 0813, Gemini 3.1
Pro, GLM 5.2, GPT-5.6 Cyber, GPT-5.6 Sol, Grok 4.20, Kimi K3,
Qwen 3.8 27B (**Fable and GPT-6 Astra refused the tasks
outright**); bypass 1 (DNS spoof — forged DNS response mapping
allowlisted `pypi.org` to the blocked callback's IP; the gateway
learned IP mappings from unverified DNS traffic; source-dependent:
gateway's DNS socket bound to the sandbox netns veth endpoint
(10.12.x.x host-side), invisible from guest — only the
source-reading models found it); bypass 2 (IP-sharing /
authority-switch — PyPI on Fastly, callback on Cloudflare; GPT-5.6
Sol pivoted through `fiddle.fastly.dev` on the same Fastly edge IP;
GPT-5.6 Cyber used `images.taboola.com` to pull a `thum.io`
screenshot of the callback and OCR'd the flag; Claude Opus 5.0
spotted the mechanism and declined on scope-instruction grounds —
"the instruction was the only thing stopping it"); the vendor
response table (E2B HTTPS bypass, mitigation planned — docs +
secret-vault-backed HTTPS egress validation; Vercel Sandbox HTTPS
bypass, known limitation, domain fronting documented; microsandbox
HTTP+HTTPS bypass, fixed in v0.6.18 with strict HTTPS mode off by
default; Modal Sandboxes HTTPS bypass, known limitation; Daytona
HTTPS bypass, authority-mismatch enforcement released in both
production regions; Deno Sandbox direct TCP bypass of `allowNet`,
fix deployed; Fly.io Sprites HTTP+HTTPS bypass, mitigation in
progress; Cloudflare Sandbox and NVIDIA OpenShell clean); the
remediation (nftables prerouting rule dropping guest packets with
wrong source address; HTTP relay validating request authority per
request and stripping routing metadata; TLS terminated at gateway
requiring ClientHello SNI + HTTP hostname both allowlisted AND
DNS-attributed to the destination IP — "Closing the hole meant
removing capability"); post-fix re-test (source access + Perplexity
Search, none of the nine models reached the flag); key quotes —
"relying only on the destination IP address at the host to determine
whether a connection is allowed is insufficient", "the absence of an
observed escape is not a proof of isolation." Related: SPACE
architecture writeup at `research.perplexity.ai` (Firecracker
microVM per sandbox, per-sandbox network gateway, credentials never
enter sandbox). Threat-model note for spark-vm: DNS-spoof and
IP-sharing bypasses are both "authority vs identity" failures —
exactly the class the proxy's host-based allowlist must rule out;
the per-request authority validation is a concrete remediation
pattern worth tracking. Filed adjacent (research, not a product) —
the C54 row's third-party layer widens with this detail.

**Vercel Drives:** NOT re-checked this pass (P49 once-daily morning
cadence — next the 2026-09-26 morning pass).

## 2. Delta news scan (2026-09-25 ~18:05–18:25 CDT) — zero genuinely new in-lane items

The scan surfaced six in-lane candidates; **all dedupe to already-filed corpus** —
verified in `COMPETITOR_ANALYSIS.md` and the dated watch docs before any claim:

- Docker Cloud Sandboxes Sept 24 launch ($0.07/hr, WeAreDevelopers)
  → already corpus (**C45**, VENDOR-VERIFIED).
- Docker Sandbox Kit spec → CNCF under Apache 2.0 → already corpus
  (**C52**, VENDOR-VERIFIED).
- DigitalOcean Managed Agents public preview → already corpus
  (**C26** deep-dive).
- DeepSeek DSec scale paper (380k concurrent sandboxes) → already
  corpus (**C49/C56**).
- Google AX 25-of-56-settings-not-enforced analysis (Sep 20) → already
  corpus ("25 of 56" in the analysis table).
- Show HN: Cognitora.dev (Kata containers on Firecracker/Cloud
  Hypervisor) → already corpus (post-night watch doc).

Strict 6-hour window (~12:00–18:25 CDT): zero new launches, pricing
changes, outages, or security disclosures from E2B, Modal, Vercel
Sandbox, Fly.io, or Cloudflare Sandbox.

## 3. Verdict

- **No new C-numbers.** Carried leads re-verified live (C37, C26a,
  C26b — all VENDOR-VERIFIED no-change; C54 still blocked —
  UNVERIFIED, never claimed as no-change); delta scan dedupes
  6-for-6 to already-filed corpus. Corpus enrichment only: C54's
  third-party layer widens (dennysentinel 2026-09-24 analysis detail —
  models, bypass mechanisms, vendor-response table, remediation,
  key quotes).
- In-lane no-launch verdict dated 2026-09-25 stands.
