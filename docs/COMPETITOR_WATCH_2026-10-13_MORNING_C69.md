# Competitor watch — 2026-10-13 (morning, cycle 69)

**Two-surveyor pass — P77 PRE-SCREEN-TRIGGERED FULL PASS.** Surveyor A:
first-party vendor re-verification against the cycle-68 baseline —
**17 VERIFIED NO-CHANGE, 1 VERIFIED DELTA, 0 UNVERIFIED** (26 opens /
25 successful fetches / 1 established failure (HTTP 404 on
`boat.dev/pricing`, 10th consecutive cycle) / 0 retries / 6
URL-recovery searches, never used as evidence; 18 enumerated items
(18 fetches + the established 404 re-confirmation inside 7b) + 1
out-of-list read (4-extra, public-beta Drives page) + 4
reconciliation reads (Microsoft Execution Containers GA blog, Modal
Runtime Roundup blog, AWS security bulletins listing, AWS
2026-127-AWS bulletin detail) + 2 out-of-list reads (docs sitemap;
the misfired 2026-126 bulletin read — no corpus bearing)). Surveyor B: delta
news scan — **0 CANDIDATES / 15 clean dedupes / 17 flagged-only** (15
searches, 15 successful / 0 failed, 0 page opens — no fold-gate
candidate; one pre-window first-party security sighting flagged to
the A-lane for reconciliation and vendor-verified in-lane).
**Corpus move this cycle: 2 new filings (C78, C79), 1 fold, 1
watch-doc delta.** Captures:
`hidden_files/agent_notes/surveyor-a|b-20261013-0910.md` (loop working
notes, in the goal workspace — not part of this repo).

> **Timestamp provenance note:** the standing rule (no per-read times
> in capture bodies) held this cycle. All verdicts below are
> mtime-bounded (stat-certified by the integrator from the capture
> mtimes, 2026-10-13 ~09:1x–~10:0x CDT).
>
> **Count-honesty check:** surveyor A's self-reported header (17
> VERIFIED NO-CHANGE, 1 DELTA, 0 UNVERIFIED) reconciles exactly with
> its 18 item enumerations and its fetch stats (25 successful reads =
> 18 enumerated fetches + 1 out-of-list 4-extra read + 4
> reconciliation reads + 2 out-of-list reads; the 26th open is the
> established `boat.dev/pricing` 404 re-confirmation, documented
> inside item 7b). Surveyor B's capture enumerates exactly
> 0 candidates + 15 dedupes + 17 flagged-only, reconciling with its
> header and search stats. Corpus-number integrity: last issued
> C-number C77; this cycle issues C78 and C79 — exactly two forward.

## Corpus moves: filings + fold

**(C78) Microsoft Execution Containers (MXC) — new filing,
VENDOR-VERIFIED.** First-party Windows Developer Blog post dated
2026-10-07 (page opened and read in full): "Microsoft Execution
Containers (MXC), now generally available, provides the containment
layer" — a policy-driven containment layer for AI agents and other
untrusted workloads. Developers and IT administrators define the
resources (files, network destinations) a workload may use; MXC
enforces the boundary at runtime with the appropriate backend; the
policy stays outside the agent workload's control, so the agent or
generated code cannot grant itself additional access. Backends:
process container (Windows 11, macOS, Linux — AppContainer / Seatbelt
/ Bubblewrap); session container (Windows 11 only — separate
OS-isolated session with its own local agent identity, isolated
desktop/clipboard/UI/input); WSL container (Windows 11); microVM
(Windows 11 and Linux, experimental). Unified JSON policy schema and
multi-language SDK; three operating modes: Enforcement, Learning,
Permissive. Windows 365 support for MXC is also generally available;
Intune management of MXC process containers is "will soon be
available"; Entra agent-attribution is "coming soon" (the identity
half is not GA). Integrations live at GA: GitHub Copilot, OpenClaw,
OpenAI Codex, Replit, LM Studio, Unsloth AI; announced as coming:
Anthropic Claude Code, Box, Manus, Perplexity, Raycast, Simular,
others. This is a new tracked vendor surface — the corpus's existing
Microsoft row (C50, Copilot Managed Runtime, tenant-scoped) is a
distinct product, so MXC gets its own filing. spark-vm relevance: the
largest platform vendor now ships an OS-enforced agent boundary with
a developer-declared policy model — the closest industrial analogue
to spark-vm's own boundary thinking (human-declared authority,
enforcement outside the agent); the Learning/Permissive modes are
policy-authoring color for any agent-permission surface.

**(C79) AWS security bulletin 2026-127-AWS — new filing,
VENDOR-VERIFIED.** First-party AWS security bulletins listing (read
in full) confirms bulletin 2026-127-AWS (Important, published
2026-10-06 13:30 PM PDT); the bulletin detail page (opened and read
in full) covers two issues in `bedrock-agentcore-starter-toolkit`
(affected versions >= 0.1.4 and <= 0.3.13; fixed in 0.3.14):
**CVE-2026-105812** — code injection ("might allow an authenticated
same-account actor to execute arbitrary code when a user imports and
runs or deploys a Bedrock Agent, via crafted configuration values
incorporated into generated Python source without safe literal
encoding"; CVSS 3.1 9.0 per the vendor GHSA GHSA-37r5-8xpw-vxp9);
**CVE-2026-106032** — external-reference handling ("crafted external
reference values in the OpenAPI content associated with a Bedrock
Agent action group can cause unintended outbound requests and local
file access during agent import"; CVSS 5.7; vendor GHSA
GHSA-5xmr-2rcp-3j75). Resolution: upgrade to 0.3.14; agents imported
with an affected version must be re-imported and their local and
deployed output artifacts replaced (fix does not retroactively clean
generated artifacts). The toolkit has been deprecated since
2026-03-27; the recommended long-term action is migrating to the
AgentCore CLI (`@aws/agentcore`), which contains the equivalent fix
for the same issue class. This pair is distinct from the C66-introduced (C67-carried)
flagged-only pair (CVE-2026-12530/CVE-2026-16796, third-party-only,
no AWS bulletin) — first-party provenance is the filing bar, and
this bulletin clears it. spark-vm relevance: another observed
instance of the agent-*metadata*-pasted-into-generated-source hazard
class the third-party trackers flag as recurring in the AgentCore
tooling (the severitydaily recap notes the same class in the
AgentCore CLI's `collaborationInstruction` path) — a standing
hazard pattern for any tool that turns agent/harness metadata into
code; swapd's boundary posture treats all agent-supplied strings as
untrusted by construction.

**Modal fold — VM Sandboxes launch + Sandbox Sidecars + Modal Clusters GA
(VENDOR-VERIFIED, folded into the Modal corpus row per the C32
primary-source-verification fold precedent; no new C-number).**
First-party modal.com "Runtime Roundup" blog (Runtime keynote recap,
page opened and read in full): **VM Sandboxes** — "give your agent
access to a full Linux computer"; launched at the Runtime keynote
and already in use at customers Linear, Legora, and Snorkel powering
coding agents and evals (this graduates the corpus isolation table's
standing "a VM-sandbox alpha now exists" note to a launched product;
the blog uses no explicit "generally available" language for this
one — the GA-language bar is held); **Sandbox Sidecars** — containers that run
alongside the main Sandbox on the same host "with the same isolation
as separate sandboxes": agent-generated code runs in the main Sandbox
while credentials, proxies, harness logic, or other trusted
operations run in a Sidecar the agent cannot directly access, with
host-local communication (the Sidecar shape is the closest
vendor-side analogue to spark-vm's own harness/agent separation —
trusted ops isolated from agent-reachable code, with the credential
path kept outside the agent boundary); **Modal Clusters** — GA via
`@modal.clustered` (multi-node GPU clusters; first-party
confirmation of the 2026-10-01 third-party report); Endpoint
Candidates in private beta, GA soon.

## A-lane deltas (watch-doc deltas, not filings)

**Daytona V0.224.0 — new top release** (first-party
`daytona.io/changelog`, read in full). Dated OCT 12 2026, above OCT
07 2026 / V0.223.0 ("Mouse and keyboard hold endpoints in all SDKs").
"Per-call region for sandbox and snapshot create": SDK callers can
set the region on each sandbox and snapshot create call; plus PTY
and log streaming behavior fixes in the Python and TypeScript SDKs.
Sequence below intact (V0.222.0, V0.220.0, V0.218.0...). Per the
V0.220.0/V0.222.0 precedent: a maintenance/feature release in the
established rapid cadence — recorded, no new C-number, no
sandbox-surface structural move.

## B-lane (0 candidates)

**C11 FILE ON CLOSE — armed, NOT triggered.** Modal $750M (Accel,
$15.75B — "nearing"/"closing in on"/"close to"; bytevyte: "Neither
round has closed") and Baseten ~$26B ("valuations under discussion,
not closed rounds"; "have not produced completed rounds") both still
unclosed across all recrawled sources. No company-issued close
announcement anywhere this pass.

**Clean dedupes (15):** C11 Modal (no close — language unchanged);
C11 Baseten (no close); C76 Vercel KVM zero-day (no CVE in public
databases, no write-up, no patch as of the mid-October third-party
FAQs — gate still open); Vercel Drives (no GA language); DO Agent
Droplets (Oct-1 launch recrawls only, public preview posture; the
devops-daily billing analysis is third-party); Daytona (no vendor
news newer than V0.223.0 in-window — the B lane's Daytona third-party
recrawl is pre-window release color); E2B (third-party noise only);
Docker Sandboxes (v0.47.0 recrawl matches C67; Sandbox Kit Spec CNCF
"formally submitted later this fall" is a plan, not news); Modal
egress billing (no third-party went-live signal — first-party
re-confirm remains Surveyor A's lane); Zenity "AgentCorruption" (AWS
spokesperson still disputes characterization as "expected and
documented behavior"; Zenity says fully mitigated — state unchanged
from C68, no AWS bulletin); OpenAI training-agent DNS-escape (pause
holds per third-party recaps, no resume date); Perplexity SPACE (Part
II still upcoming; "How we engineer safer agents" is a principles
recap, not Part II); Cloudflare Containers/Sandbox (third-party
comparison color only); NanoCo (no first-party product/pricing/docs
material — re-grade bar still unmet); AWS Strands Box (C77 — no
follow-through in window; still developer preview, macOS
Apple-silicon only; dedupe against the C66 fold).

**Flagged-only (17):** C79 AWS bulletin 2026-127-AWS (reconciled
in-lane this cycle — filed above); C78 Microsoft Execution
Containers GA (reconciled in-lane this cycle — filed above); Modal VM
Sandboxes GA + Sidecars (reconciled in-lane this cycle — folded
above); Agent37 ($0.37/month sandbox, YC F26 — in-window
third-party-only micro-launch, no first-party launch URL surfaced,
thin provenance); devops-daily "Where to Run AI Agents: 8 Managed
Agent Runtimes Compared" (third-party comparison asserting
unverified GA claims for Google Agent Runtime and Microsoft Foundry
hosted agents — flagged-only, not filed); Perplexity SPACE Part II;
OpenAI training-agent DNS-escape resume outcome; Strands Box
follow-through (GA / multi-OS / AgentCore deployment — still
developer preview, macOS Apple-silicon only, Linux in development
without a date); AgentCore SDK CVEs CVE-2026-12530/CVE-2026-16796
(no new AWS advisory — restatements of the BeyondTrust Sept-28
disclosure); NanoCo re-grade watch; Hugo CVE-2026-100690
(third-party-only); Vercel Sandbox Oct-6 minor incident; Docker $250
Agent Challenge (through 2026-10-31); Docker Sandbox Kit CNCF spec
plan; alleged Vercel dark-web credential sale (UNCONFIRMED); Modal
July compromise (resolved/watch-only); Modal multi-node GPU clusters
GA (carried as training/inference compute color — first-party
confirmed this cycle via the Runtime Roundup, but the Modal row fold
above carries it).

## Standing-item state

- **C11 FILE ON CLOSE — armed, gate NOT triggered** (69th
  pre-screen cycle; both arms still unclosed).
- **C12 — OPEN (69th consecutive first-party read).**
  AgentComputer publishes no egress pricing line.
- **C76 gate (CVE / technical write-up / patch disclosure) — NOT
  advanced.** No CVE in public databases, no write-up, no patch.
- **C77 Strands Box — filed, no movement** (no post-preview repo
  release, GA, or AgentCore follow-through sighted this pass).
- **C78 Microsoft Execution Containers — filed this cycle**
  (vendor-verified GA 2026-10-07).
- **C79 AWS bulletin 2026-127-AWS — filed this cycle**
  (vendor-verified; CVE-2026-105812 9.0 + CVE-2026-106032 5.7).
- **Modal egress billing — EFFECTIVE 2026-10-01.** First-party page
  tracked fields verbatim; no went-live banner; first bill including
  egress still postured for November 1, 2026.
- **Vercel Drives GA — standing tracked, not filed.** No GA language
  on any first-party page (private-beta page, public-beta page,
  sandbox docs `last_updated: 2026-09-22`, dated changelog index —
  all still pre-GA).
- **Hugo CVE-2026-100690 — third-party-only** (file on first-party
  gohugoio GHSA only).
- **NanoCo re-grade bar — still unmet** (no first-party material).
- **Perplexity SPACE — flagged-only carry; watch for Part II.**
- **C72 / C73 / C74 / C75 — FILED, no movement;** C76 filed, gate
  item open. C73 fold stands (Bedrock Managed Agents preview).
- **DigitalOcean URL-host watch-note:** pricing + limits canonicals
  at `docs.digitalocean.com/.../details/pricing/` and
  `.../details/limits/`; the pricing page's own "Limits" link
  resolves to the regional availability page (generated 10 Oct
  2026) — next slot keeps the direct limits canonical (as this one
  did).
- **Vercel sitemap count-field — not re-runnable this cycle** (the
  only corpus-verbatim sitemap outlink serves the DOCS sitemap
  `vercel.com/docs/sitemap`, not the changelog sitemap; no verbatim
  changelog-sitemap URL in corpus material). Last resolved state
  stands (C66: 1397→1401 math). Not graded.
- **Aged out stay out:** C29, C45, C56, C66, C67, C62, Heapjack/
  Overpatch, GitLab CVE-2026-85706, Dextr AI; C26 closed. No
  age-out movements this pass; no re-folds.

## Zero-fabrication statement

Every verdict above is grounded in a first-party page actually
opened in this pass (A lane: 26 opens, 25 single first-try fetches
with zero retries, 1 established HTTP-404 on `boat.dev/pricing`
confirmed a 10th consecutive cycle — the 404 is the established
evidence) or in an observed search-result snippet cited with its
source and date context (B lane: 15 searches, 15 successful / 0
failed, 0 page opens — no fold-gate candidate). The 6 URL-recovery
searches (MXC blog, Modal roundup blog, 3 AWS-bulletin searches, the
bulletins-listing open that misfired to the adjacent 2026-126
bulletin) were never used as evidence; the reconciled items were
each verified by
opening and reading the first-party page in full. No page demanded
auth; no logins were performed. No repo, branch, or PR was touched
except as described in the ship path below.

**Ship path:** isolated worktree
`repo-strategy-compwatch-20261013-0910` (goal level; removed
post-merge per P20); Data-API push; draft PR opened pre-review;
CI on the exact head; squash-merge in dependency order per the
playbook's ship rules.
