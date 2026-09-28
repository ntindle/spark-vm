# Competitor watch — 2026-09-27 (late-evening, cycle 5)

Scoped verification turn, NOT a full two-surveyor pass. Two delegated items
from the evening cycle-3 doc's standing asks, both read-only, no login, no
writes:

1. **The NanoClaw/NanoCo parent call** (cycle-3 watch-out #4): "if NanoCo
   ships a sandbox/compute product or a first-party announcement surfaces,
   re-grade from flagged-only." A first-party surface now read — the answer
   is that no re-grading is warranted.
2. **The deferred watch-review nits (BACKLOG L1674, (a)–(f))** — "adopt at the
   next watch pass's convenience": re-verified each nit's adoption status
   against the live corpus and fresh first-party evidence; the one nit left
   unadopted ((e), the deprecated-row expiry rule) is codified in this pass.

Delta-only against the cycle-4 scoped verification
(`docs/COMPETITOR_WATCH_2026-09-27_EVENING_C4.md`). No other vendor
re-checks — the cycle-3 baseline (~18:26–~18:55 CDT, fast movers + pricing
9/9 VENDOR-VERIFIED NO-CHANGE) and the C4 Modal fold stand.

## NanoCo/NanoClaw — first-party read (VENDOR-VERIFIED ~20:38 CDT 2026-09-27)

`https://nanoclaw.dev` — NanoCo's own site, read live this turn:

- NanoClaw is "a lightweight, open-source **personal AI agent that runs on
  your own machine**" (MIT license) — it connects to messaging apps
  (WhatsApp, Telegram, Slack, Discord, Signal, …), runs every active agent
  session inside an isolated Docker container, and routes credentials through
  OneCLI's Agent Vault by default so agents never hold raw API keys.
- Architecture: one Node.js host process + one Docker container per active
  session + SQLite queues across the boundary. Docker is the only supported
  container runtime (macOS, Linux, Windows via WSL2).
- The site's own comparison table pitches NanoClaw against OpenClaw as an
  *agent framework* (200 vs 3,680 runtime TypeScript files, OS-container
  isolation vs application-level checks) — not against sandbox/compute
  providers.

**Verdict: parent call closed — no sandbox/compute product.** NanoCo ships
an agent-framework product (the NanoClaw personal agent), not hosted
sandbox or compute infrastructure. Its only lane touchpoint is as a
*consumer* of other people's sandboxes: NanoClaw runs inside Docker
Sandboxes (per the third-party Docker partnership coverage) and is already
named as an ecosystem collaborator on Docker's Sandbox Kit Spec in the
corpus Docker row (`docs/COMPETITOR_ANALYSIS.md` — "Ecosystem collaborators
named: AWS, Box, Datadog, Dynatrace, JFrog, **NanoClaw**, OpenClaw, Palo Alto
Networks, Snyk"). No watch line-item opened; the entity stays flagged-only;
no corpus fold (the Docker-side pointer already exists).

Third-party corroboration (en.wedoany.com 2h recrawl, techinasia via
TechCrunch): NanoCo raised a $12M seed round led by Valley Capital Partners
(backers include Docker, Vercel, Monday.com, Slow Ventures, Clem Delangue);
founders declined a ~$20M acquisition offer. Consistent with an
agent-framework company, not an infra provider. THIRD-PARTY layer only —
no corpus move.

## Watch-review nits — re-verification sweep (BACKLOG L1674)

Each nit's standing adoption status checked against the live corpus this
pass:

- **(a) C36 recent-color sentence labeling — CHECKED, still clean.** The
  2026-09-24-late-morning pass found no unlabeled C36 claims; this pass
  re-grepped every `C36` mention in the corpus — all remaining occurrences
  are cross-references to the labeled field-table row and watch-update
  sections, not new claims. No edit made.
- **(b) Upstash Box "future-vetting candidate" C31 cross-reference —
  ADOPTED (stands).** The 2026-09-23 late-night README watch-table row
  carries it; verified still present.
- **(c) YC 301 rename evidence — ALREADY ADOPTED; re-verified live this
  turn.** The tracked-set Boat row cites `ycombinator.com/companies/ascii`
  → 301 → `/companies/boat`. Re-read ~20:33 CDT 2026-09-27: `curl` returns
  `301 -> https://www.ycombinator.com/companies/boat`. Evidence still live.
- **(d) DE/FI/FR geography orphan — ADOPTED (stands).** The EU-only DE/FI/FR
  datapoint is folded in the tracked-set Boat row's pricing cell; the
  deprecated C40 row retains it only for provenance.
- **(e) Deprecated-row expiry convention — ADOPTED THIS TURN.** The
  2026-09-24-late-morning pass punted codification as "unilateral rule
  adoption pending corpus-owner approval". The backlog item explicitly
  requests codification, there is no separate corpus owner (the loop maintains
  the corpus; PLAYBOOK.md is not amended by this change), and the convention
  is reversible — so it is codified below in the Corpus conventions section.
  It authorizes no deletion by itself: removal of a deprecated row remains a
  decision of a consolidation pass, which is the only venue that can weigh
  provenance retention against corpus hygiene.
- **(f) YC-slug live-resolve parenthetical — ADOPTED (stands).** The C40
  rename section notes the slug still live-resolves to the Boat page; (c)'s
  fresh re-verification corroborates it.

## Corpus fold

- **Corpus conventions gain the deprecated-row expiry rule** (nit (e)):
  a `DEPRECATED ROW` is retained for provenance; once its unique facts are
  folded into the canonical row it becomes a *removal candidate*, and only a
  consolidation pass may remove it. The C40 row is now explicitly tagged as
  the rule's first standing candidate (its facts are folded; removal decision
  belongs to a future consolidation pass).
- No new C-numbers. No other corpus edits.

## Not done this turn

No other vendor re-checks (cycle-3 + C4 baselines stand). The remaining
cycle-3 watch-outs (DevDay outcome check in Sep-29 slots — "agent O" echo
wave still UNCONFIRMED; Hugo CVE-2026-100690 GHSA sweep; CVE-2026-93993
parent call) carry forward unchanged. In-lane no-launch verdict dated
2026-09-25 stands.
