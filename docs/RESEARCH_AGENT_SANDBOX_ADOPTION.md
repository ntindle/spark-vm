# How hosted agent-sandbox products actually get used
## Product research — 2026-09-18

**Question:** how do hosted agent-sandbox/VM products actually get used?
What does a user do first, where does signup friction bite, and what makes
one stick? **Method:** public sources (product docs, launch posts, developer
field notes, one open-source onboarding spec) surveyed 2026-09-18. Findings
are numbered; each carries its evidence and the implication for hosted
spark-vm. This is a strategy input, not a spec — it feeds the backlog and the
gap analysis, not the implementation.

**Scope note:** this research is about the *hosted product* track (a Muse
signs up and gets a box). The open-source track has a different audience
(contributors) and is covered separately. Where the doc says "the signup
doc" or "PR #24," it means the hosted signup/onboarding design
(`docs/HOSTED_SIGNUP_ONBOARDING.md`, open as PR #24): the ed25519 +
human-fingerprint-approval identity flow, provider-agnostic provisioning,
SSH relay, and short-lived certs.

## Limitations (read this before the findings)

Every numbered finding below rests on evidence about **human developers**
adopting sandbox products — SDK READMEs, developer field notes, a
human-first product launch. Not one source involves a Muse (or any agent)
signing itself up for a hosted box. The transfer of these findings to the
*Muse-as-customer* model is a hypothesis, not a result. In particular the
doc does not model the **buyer-vs-user split**: a Muse holds no credit
card, so the buyer is a human or org whose purchasing criteria (audit
trails, compliance, cost controls, SSO) appear nowhere in this research.
R7 below exists to close that gap before any finding hardens into a spec.

---

## Finding 1 — The adoption gate is one tiny task, not a feature list

In the SDK-first developer-tool segment, the products that convert make the
first run a single bounded action, not a tour of capabilities:

- **E2B** — the entire first run is three steps: `npm i`/`pip install`,
  copy an API key from the dashboard into an env var, run the quickstart
  snippet. Nothing else is asked of you.
  ([E2B SDK README](https://github.com/e2b-dev/e2b))
- **Daytona** — the canonical first sandbox is a flat one-liner:
  `sandbox = daytona.create()`.
  ([Daytona README](https://github.com/daytonaio/daytona))
- **A practitioner's checklist** for trying any sandbox runtime with an
  agent host is explicitly *not* a feature list: "whether this task actually
  needs code execution; whether it needs network; whether it needs
  filesystem access; whether credentials are involved; the smallest
  reversible verification fixture; timeout, cleanup, and artifact export
  plan."
  ([Tangweigang, Jun 2026](https://medium.com/@tangweigang/before-an-agent-runs-code-in-e2b-define-the-sandbox-contract-first-15c8c28e6060))

**Implication for spark-vm:** in the SDK-first segment, the hosted first run
must be one command and one verifiable result — if it asks the user to
configure anything beyond identity, it loses to E2B's three steps. **But**
the persistent-box segment behaves differently (see Finding 6): TermSquad's
first session is dashboard-first and multi-step — install agents, connect
accounts/API keys — and that is the flow of the offering closest to ours.
So the qualified takeaway: the *time-to-first-verifiable-result* is what
converts, and in our segment users tolerate a longer first session when the
payoff (bring your agents, bring your keys, keep your state) is visible up
front. The signup doc's §8 (first-run: smoke checks, then "the first real
job — the aha moment in minute ten") is already shaped this way; it should
stay that way and not be "simplified" into an SDK-style quickstart that
skips the parts that make the box *theirs*.

## Finding 2 — Pre-seeded state beats onboarding docs

Two independent field reports show the same failure mode: a fresh box that
drops the user into a *first-run picker* kills the "it just works" moment,
and the fix is always baking state, not writing docs.

- **agentbox/E2B:** `agentbox e2b claude` dropped users into Claude's
  first-run theme picker because E2B boxes didn't bake `_claude.json` at
  prepare time. The author calls this **"THE BLOCKER"** and fixed it by
  overlaying the host's onboarding state onto every created box, plus a
  `e2b-box auth` one-time step so "your first box comes up authenticated
  instead of on the agent's own sign-in screen."
  ([agentbox PR #53](https://github.com/madarco/agentbox/pull/53),
  [herdr-e2b-sandbox README](https://github.com/e2b-dev/herdr-e2b-sandbox))
- **GSA's acq quickstart** ships a documented "First-Run Snags" section — the
  pattern for the failures you *can't* pre-seed (missing `./acq` on PATH,
  macOS developer-tools install). The top-2-snags list is the product, not
  the full manual.
  ([gsa-tts/agentic-coding-quickstart](https://github.com/gsa-tts/agentic-coding-quickstart))

**Implication for spark-vm:** the hosted provisioning pipeline must
pre-seed the agent harness's onboarding state into the golden image (or
inject it at provision time) so the first session never shows a setup
wizard. Whatever *can't* be pre-seeded belongs in a top-3 snags list on the
welcome page, not in a 40-page guide. This extends the signup doc's
provisioning and first-run sections (§6–§8 — provisioning sequence,
cloud-init-vs-golden-image, and the first-10-minutes flow): "provisioned"
must mean "ready to work," and the doc should say so explicitly.

## Finding 3 — Persistence is the validated headline; every task-scoped sandbox loses state by design

The task-scoped incumbents all lose state or cap it, and a competitor just
launched with persistence as the entire pitch:

- **E2B** sandboxes are task-scoped by design: 1-hour sessions on Hobby,
  24 hours on Pro; compute caps at 1–8 vCPU / 512 MB–8 GB; pause/resume is
  still in beta; no GPU.
  ([sandbox reference](https://github.com/claytonfarr/ralph-playbook/blob/HEAD/references/sandbox-environments.md),
  [StartupHub 2026 comparison](https://www.startuphub.ai/ai-news/artificial-intelligence/2026/daytona-vs-e2b-vs-modal-vs-vercel-sandbox-2026))
- **Cloud Run Sandbox** (Jul 2026): "The box has amnesia on purpose. The
  filesystem is a read-only view of your container, and writes land in a
  throwaway overlay that is gone when the box exits."
  ([Sascha Heyer](https://medium.com/google-cloud/let-your-agent-run-its-own-code-inside-a-cloud-run-sandbox-965633fb7f0c))
- **TermSquad launched 2026-09-15** (three days before this writing) as an
  *"always-on cloud computer for AI coding agents"* — and its launch message
  is persistence all the way down: persistent sessions, shared project
  memory, "Closing the browser does not end those sessions." That is the
  pitch because that is the gap.
  ([EINPresswire release, via lifestyle.independent.mk](https://lifestyle.independent.mk/story/785982/termsquad-launches-an-always-on-cloud-computer-for-ai-coding-agents/))
- **Microsoft Foundry** (Sep 2026) is shipping "durable, long running agents
  — surviving container crashes, redeployments, and periods of inactivity
  with automatic recovery."
  ([Foundry blog](https://devblogs.microsoft.com/foundry/hosted-agents-build26/))
- Counter-evidence, honestly noted: **Daytona's README claims "Unlimited
  Persistence: Your Sandboxes can live forever."** The persistence
  differentiator is therefore not "we have state and they don't" — it is a
  *real persistent VM*: full OS, unattended background jobs, your own stack
  and cron loops, no session clock at all. Against task-scoped sandboxes
  that is still a clean win; against Daytona's persistence claim the win
  has to be argued on the VM-ness, not the state-ness.

**Implication for spark-vm:** "a permanent home for your Muse" is the
market-validated headline — a new competitor just launched into exactly
this gap — and it must lead every hosted surface: landing copy, README,
first-run messaging (R5). The honest version survives the Daytona
counter-evidence: the headline is *a real computer that stays yours*, not
merely "we keep state."

## Finding 4 — Per-action friction survives; blanket lockdown gets abandoned

A May 2026 field note on Claude Code + microVM sandboxing: wrapping *every*
agent invocation in a sandbox "kills adoption within weeks," because the
host integrations that make the agent useful (IDE plugins, browser MCPs,
ssh-agent, biometric unlock, existing creds) don't work inside the box.
Per-trigger opt-in — sandbox the risky sessions, leave the rest — is "the
design that survives daily use": "an abandoned security tool provides zero
protection."
([tieubao, May 2026](https://github.com/tieubao/til/blob/HEAD/notes/coding-agents/opt-in-beats-all-in-for-coding-agent-sandboxing.md))

**Implication for spark-vm:** this is *directional* support for per-action
friction over blanket lockdown — not an architectural validation. The
mechanisms differ: tieubao **isolates** risky *sessions* (a separate
execution context), while our design **authorizes** risky *actions* via
confirmd (the approvals service — mobile-friendly page today, push
notifications still to come per the signup doc's open questions), which
then execute on the same persistent box. An approved-but-malicious action
is not sandboxed. Do not let this finding steer the H5 sentinel design
toward an approval role: per the signup doc §10, sentinel is the *outside
observer* (flow logs, hypervisor telemetry, signed audit batches) plus the
kill-switch path — it watches from the outside, it does not approve. The
product copy should say the honest version: *your box is yours — the
guardrails engage per action, not per session* (keep both clauses together;
"yours" alone reads as no-oversight, which undercuts the trust story the
positioning depends on).

## Finding 5 — The secrets-injection posture is being independently re-derived

GSA's `acq` quickstart: "`acq` injects secrets into the sandbox at
runtime — the real values **never enter the guest**." That is the same
*posture* as spark-vm's sentinel/swapd design — placeholders in
agent-visible config, real values substituted where the agent can't see
them — arrived at independently. Note the mechanism differs: acq injects
at runtime; swapd swaps at the egress proxy. Same posture (the agent never
sees raw values), different implementation.
([gsa-tts/agentic-coding-quickstart](https://github.com/gsa-tts/agentic-coding-quickstart))

A BYOK/managed-credit onboarding spec from the Proliferate project states the
product promise explicitly: "If the user has free managed credit, it works
immediately. If the team has BYOK configured, the sandbox uses the team's
key through Bifrost without exposing the raw provider secret."
([proliferate/bifrost BYOK spec](https://github.com/keystonebot/proliferate/blob/HEAD/docs/architecture/bifrost-byok-onboarding-spec.md))

Corroborating signal on the egress half: E2B now documents
`allowInternetAccess` plus `network.allowOut`/`network.denyOut` for
granular CIDR/domain filtering — explicit egress control is becoming table
stakes, which is where our allowlist proxy plays.
([sandbox reference](https://github.com/claytonfarr/ralph-playbook/blob/HEAD/references/sandbox-environments.md))

**Implication for spark-vm:** two data points are *not* convergence — the
security docs should not claim the ecosystem is landing here until we check
how E2B/Daytona handle secrets at scale. What the finding does support is
framing: the placeholder-swap architecture is an independently re-derived
posture, not a quirky home-grown choice, and that framing belongs in the
security docs once corroborated (R6). Separately, the hosted signup funnel
wants the same two-lane shape as the BYOK spec: a free tier that "just
works" the moment signup completes, and a BYOK lane where the human's own
credentials are installed without the agent ever seeing raw values
(cred-ui already does this; the hosted version needs the same guarantee).

## Finding 6 — What users do first: install *their* agents, connect *their* keys

TermSquad's launch describes the first session concretely: "Users install
their chosen agents from the dashboard and connect existing accounts,
subscriptions or API keys as supported by each tool." Not "learn our agent" —
*bring yours*.
([EINPresswire release, via lifestyle.independent.mk](https://lifestyle.independent.mk/story/785982/termsquad-launches-an-always-on-cloud-computer-for-ai-coding-agents/))

Combined with Finding 1's qualified takeaway, the hosted first-10-minutes
for spark-vm drafts itself (and the signup doc's §8 already sketches it):

1. Sign up: human creates the account, names the box, copies the
   enrollment token to their Muse, approves the key fingerprint.
2. One command provisions the box; the harness arrives pre-authenticated
   (Finding 2). Caveat, inline: MVP provisioning is ~15 minutes of
   cloud-init (signup doc §5/§7) — the "first 10 minutes" clock starts at
   box-ready, not at signup, and the signup page must say so.
3. The Muse runs smoke checks, then one approval-gated action; the human
   approves it from the approvals page (push notifications still to come,
   §11.4). The aha moment is *the approval loop working*, not the VM
   existing.
4. Everything after is theirs: repos, cron loops, Muse jobs.

**The friction the research question asked for, honestly named:** per the
signup doc §4–§5, the human's key-fingerprint approval **gates**
provisioning, and it recurs on every re-link for ephemeral Muses. That
human ceremony is the single biggest signup-friction item against
Finding 1's thesis — "beyond identity" in Finding 1 quietly excluded it
from the E2B comparison, and E2B asks for nothing comparable. Either R4
scopes the free tier to "works immediately *after key approval*," or a
later design proposes a structural fix (provision on token, gate only cert
issuance; or a warm pool) — and any frictionless tier has to survive the
signup doc's own abuse constraint (§11.7: email-only invites invite spam
VMs; decide before launch).

**Implication for spark-vm:** the signup doc covers identity and
provisioning but the first-run spec deserves its own follow-up with the
exact commands, the approval-loop aha moment, and "done" criteria — that
is R1.

## Finding 7 — Competitive map, September 2026

| Offering | Model | Where it wins | Where it lags for our user |
|---|---|---|---|
| **TermSquad** (launched Sep 15, 2026) | Always-on cloud computer for coding agents; Herdr (the session/workspace manager it builds on) sessions; dashboard + SSH + mobile web terminal | Persistence story, multi-agent orchestration, human-first dashboard | Brand-new, unproven at scale; human-developer framing, not agent-as-customer |
| **E2B** | Ephemeral code-execution sandboxes, SDK-first | 3-step DX, templates-as-code, documented egress controls (`allowOut`/`denyOut`) | Task-scoped by design (1h/24h sessions), 1–8 vCPU / 512 MB–8 GB caps, no GPU, pause/resume still beta |
| **Daytona** | Agent dev environments, `daytona.create()` | One-liner ergonomics, declarative builder, claims unlimited persistence | Lifecycle management to configure; dev-environment framing, not a personal box |
| **Modal** | Serverless compute | GPU in-sandbox (T4–H100), sub-second cold starts | Not an agent home; function-scoped |
| **Microsoft Foundry hosted agents** | Enterprise agent platform | Durable agents, portal observability | Enterprise-shaped; not a personal box |
| **DIY floor** | $5.70/mo DigitalOcean droplet + agent-deck/orca | Price | The human does everything; no approvals, no credential proxy, no push |
| **Replit / Codespaces / Coder** | Cloud dev environments | Familiar | Built for humans typing, not agents living |

([TermSquad](https://lifestyle.independent.mk/story/785982/termsquad-launches-an-always-on-cloud-computer-for-ai-coding-agents/),
[E2B SDK](https://github.com/e2b-dev/e2b),
[Daytona](https://github.com/daytonaio/daytona),
[2026 sandbox comparison](https://www.startuphub.ai/ai-news/artificial-intelligence/2026/daytona-vs-e2b-vs-modal-vs-vercel-sandbox-2026),
[sandbox reference](https://github.com/claytonfarr/ralph-playbook/blob/HEAD/references/sandbox-environments.md),
[Foundry](https://devblogs.microsoft.com/foundry/hosted-agents-build26/),
[DIY $5.70/mo](https://dev.to/tamizuddin/building-a-570month-autonomous-ai-coding-agent-in-the-cloud-using-open-source-terminal-agent-22nb))

Two axes the map needs that the feature rows hide — both favor us and both
are load-bearing for the positioning:

- **Egress controls:** our allowlist proxy (swapd — the egress proxy that
  substitutes credential placeholders and enforces per-host allowlists,
  shipped and adversarially hardened) plays directly against E2B's
  `allowOut`/`denyOut`. This is the comparison the security docs (R6)
  should make concrete: same table-stakes feature, different trust story
  (placeholder-swap means the agent never holds the secret at all).
- **Isolation:** the signup doc stakes its isolation story on the per-VM
  tenant boundary ("what keeps the isolation story tractable," §9) —
  against shared-infrastructure sandboxes. That axis should be scored
  explicitly in the next competitor pass (R3).

**spark-vm's window:** no offering surveyed here offers *a persistent
personal box built for the agent as the customer* — with per-action human
approvals, credential-proxying so the agent never sees secrets, and the
human reachable for approvals. TermSquad is closest but frames the human
as the user and the agent as the tool; our signup doc frames the *Muse* as
the user. That inversion is the positioning.

**Working positioning thesis** (reconciling Finding 3 with the moat):
persistence — *a real computer that stays yours* — is the **headline**,
because that is the validated gap; the credential-proxy + human-approval
architecture (swapd + confirmd, both shipped and adversarially hardened)
is the **differentiator**, because that is what nobody else has built.
Sentinel (outside observation) is the unbuilt half of the trust story —
name it as future, not as moat.

---

## Backlog items this research creates

Worked into BACKLOG.md by this run (research archetype, 2026-09-18):

- **R1 — First-10-minutes spec** (sales/funnel follow-up): the exact hosted
  first run — commands, pre-seeded harness auth, the approval-loop aha
  moment, "done" criteria. Extends the PR #24 signup doc (§8).
- **R2 — Pre-seeded harness onboarding state** (feature): golden-image (or
  provision-time) injection of agent-harness onboarding state so no
  first-run picker ever appears; top-3 snags list for the rest.
- **R3 — TermSquad competitive watch** (competitor): track their pricing,
  session model, isolation story, and agent-as-customer story; score the
  egress-controls and isolation axes explicitly next pass.
- **R4 — Free-tier "works immediately" shape** (sales): what the free tier
  includes so signup → working box needs zero *human credential* steps —
  scoped to "after key approval" unless a structural fix lands; must
  survive the §11.7 abuse constraint. Feeds the pricing-page thinking item.
- **R5 — Persistence-as-headline positioning pass** (marketing): "a real
  computer that stays yours" leads the landing copy, README top, and
  first-run messaging.
- **R6 — Security-docs repositioning** (docs): frame placeholder-swap as an
  independently re-derived posture — only after corroborating how E2B /
  Daytona handle secrets; make the swapd-vs-`allowOut` egress comparison
  concrete.
- **R7 — Beta-Muse first-run pilot** (research): validate the Muse-as-
  customer transfer (Limitations) — instrument time-to-first-working-
  approval with a handful of beta Muses before Finding 1's shape hardens
  into spec.

## Sources

Surveyed 2026-09-18; links inline above. Primary: E2B SDK README
(e2b-dev/e2b); Daytona README (daytonaio/daytona); agentbox PR #53
(`_claude.json` pre-seeding); herdr-e2b-sandbox README (`e2b-box auth`);
gsa-tts acq quickstart (runtime secret injection, First-Run Snags);
proliferate/bifrost BYOK onboarding spec; tieubao TIL (opt-in sandboxing);
Tangweigang sandbox-contract essay; Sascha Heyer Cloud Run Sandbox sharp
edges; TermSquad launch (EINPresswire release via lifestyle.independent.mk,
Sep 15, 2026); Microsoft Foundry hosted-agents update; StartupHub 2026
sandbox comparison (Daytona vs E2B vs Modal vs Vercel); ralph-playbook
sandbox reference (E2B limits, session caps, network controls); tamizuddin
DIY agent-VM guide.
