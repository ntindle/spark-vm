# Multi-agent orchestration

**Status:** design doc — implements H8's filing step (file the shape before
marketing claims anything about teams). Companion to backlog H8 (filed from
the competitor pass, PR #26) and `docs/HOSTED_GAP_ANALYSIS.md` (which names it).

**Path convention:** all paths are from the repo root (`muse-job/` holds the
job-runner CLI).

## The gap

TermSquad ships **Squad**: a lead agent that delegates to parallel sub-agents
with shared project knowledge ("Squad Memory") — a task-scoped team, not just
an isolated box (`docs/COMPETITOR_ANALYSIS.md` §TermSquad). spark-vm's answer
today is **muse-job**: a single-operator job runner. The operator is the only
coordinator, and every job is a leaf. That is a real product gap for the hosted
vision — "give your Muse a computer" becomes "give your Muse a *team*" — and
marketing must not claim orchestration until the primitives below exist.

## Scope

Orchestration here means one job delegating to many parallel jobs, with the
coordinator able to inspect, steer, and close its leaves, and with every action
attributable to the job that performed it. It does **not** mean agent-managed
infrastructure (the operator still runs the box; `deploy/` owns services), and
it does **not** change muse-job's trust model (turn-state events are
cooperative telemetry, never ground truth — issue #3).

## The three primitives

### 1. Job fan-out

`muse-job/bin/muse-job` today spawns one job per invocation (`spawn` → slug → one
worktree + one tmux session `mjob-<slug>`). Fan-out is the same operation in
the plural, with gang-level convenience:

- `spawn-many <template-slug> --count N` (or `--jobs a,b,c`): N leaves, each
  with its own slug-derived worktree, branch, and tmux session. The worktree
  convention already isolates jobs; nothing new to invent there.
- `steer-all <selector> "<text>"` / `kill-all` / `close-all`: gang steering and
  lifecycle, where `<selector>` matches slugs by prefix or an explicit list.
- `status --gang <prefix>`: an aggregate roll-up (how many running / blocked /
  done-claimed / questions-pending) — the coordinator's one-glance view,
  built on the existing `status` + `watch` machinery.

**Concurrency semantics:** per-slug locks are held across minutes-long clones
and `flock` is non-reentrant, so gang ops are per-slug best-effort with
aggregated failure reporting — no gang-level lock. `spawn-many` acquires
per-slug locks in sorted slug order so it can't deadlock against a concurrent
gang op.

**Non-goals for phase 1:** merge orchestration (the coordinator merges leaf
branches through normal git; worktrees keep conflicts local), and a "team"
object in storage (gang = a slug-prefix convention, nothing more).

**Open question:** worktree-per-job cost at N=10+ (disk + tmux server load on
the box; event-dir fan-out under `~/.local/share/muse-job/events/`). Needs a
measured answer before the hosted product advertises a default team size.

### 2. Session sharing (coordinator as a job)

Today the coordinator is always the human operator on their box, calling
`muse-job/client/muse_job.py` over SSH. A lead agent needs the same shape:

- **Coordinator job:** a `muse-job` job whose prompt instructs it to delegate
  leaf work by running the client CLI. The client library is stdlib Python;
  inside a leaf prompt it is just a program the coordinator job can run.
  **Principal question (see open question 5):** a coordinator job running the
  manager CLI is an agent with spawn/steer/kill over sibling jobs — a new
  principal driving manager-side operations, which the manager may need to
  allowlist or role-separate.
- **Shared working memory:** today each job writes `PROGRESS.md` in its own
  worktree. A coordinator needs an aggregate view: a gang-scoped
  `<gang>.PROGRESS.md` (operator-owned, job-writable — the coordinator leaf
  writes checkpoints; the operator/coordinator can read the merge without
  entering each worktree). Contract (not enforcement): leaves write status,
  the coordinator writes decisions. **File #13 (agent-immutable protected
  sections) interacts here:** the coordinator's decision log must be
  agent-immutable against the leaves, and each leaf's workspace must be
  unwritable by other leaves. The worktree convention gives us the second;
  the first needs the #13 mechanism before coordinator jobs are anything
  more than an experiment.
- **Question channel:** the tool-shape doc (`muse-job/TOOL_INTERFACE.md` §4)
  already defines the question channel (`pending_question` /
  `wait_for_turn`). Leaf→coordinator questions ride the same channel:
  a leaf emits a `question` turn-state event, the coordinator's watch pass
  surfaces it, the coordinator steers the answer back. The plumbing exists;
  the coordinator needs the watch pass to attribute *which leaf* asked
  (see identity).

### 3. Per-job identity

Every event, decision, and audit line must carry the job that made it —
coordinator vs leaf, leaf vs leaf — or the coordinator cannot trust what it
sees.

- **Attribution primitives that exist:** `slug` (manager-side, re-pinned on
  every `load_job`), `session_uuid` (registry-bound at resume; hooks whitelist
  it in event/registration filenames), the per-job worktree (cwd checks in
  `done` triage).
- **What's missing for orchestration:**
  - A **gang/parent claim.** This **cannot** live in `job.json`: that file is
    agent-writable (issue #11) and `load_job` re-pins only `slug`, so a leaf
    could rewrite its own parentage — detach from its coordinator, attach to
    someone else's gang, or invent it. Instead, gang parentage belongs in a
    **manager-side spawn ledger** under `~/.local/share/muse-job/`
    (alongside the events dir and session registry), re-pinned on every
    `load_job` the way `slug` is. Honest residual: that ledger is
    same-user-writable, so it is consistency enforcement, not
    authentication — the exact residual language `TOOL_INTERFACE.md` already
    uses for the session registry.
  - **Spawner provenance.** When the spawner is an agent (a coordinator job
    spawning leaves through the same CLI every leaf can also run), the
    manager has no authenticated spawner identity — it cannot distinguish
    operator-spawn from coordinator-spawn from leaf-spawn. A leaf can spawn
    with `--parent <someone-else's-gang>` and pollute the gang view; the
    worktree convention does not cover the spawn plane. So `parent` is
    trustworthy only when the spawner is the operator or an
    operator-delegated coordinator; for leaves it is advisory operator-view
    bookkeeping, never a security boundary. Gang-level destructive ops
    (`close-all`, `kill-all`) must re-derive authority per slug from
    manager-controlled state, never from the `parent` claim.
  - **Per-job attribution on the question channel:** a leaf's `question`
    event names the leaf, but attribution is **advisory/consistency-checked,
    not unforgeable** (issue #3's cooperative-telemetry caveat — a leaf can
    plant a registration binding another leaf's uuid). The coordinator's
    watch pass must apply the same per-leaf triage as `watch` does for done
    claims — the event names the leaf's uuid **and** the uuid is
    registry-bound to the leaf's derived workdir at read time — before
    acting on a question. P2 ships with this advisory attribution; P4
    hardens it into audit.
  - **Audit**: `deploy/` audit lines and any future confirmd tenant
    attribution (H10) gain a `job` dimension. H8's identity layer is the
    OSS half of H10's tenant attribution.
- **Trust rule that survives fan-out:** a coordinator must apply the same
  `done`-claim triage per leaf that `watch` applies today (session uuid +
  worktree cwd + non-empty SUMMARY.md) — a coordinator may **not** trust a
  leaf's "done" line any more than the operator does. Orchestration
  multiplies the forgery surface; the triage is per-leaf, not per-gang.

## Build plan (PR-sized phases)

- **P0 — conventions (operator-only, no code):** document the manual fan-out
  recipe (naming convention `<gang>-<leaf>`, gang PROGRESS.md template,
  per-leaf triage checklist) in `muse-job/README.md`. Shippable as docs.
- **P1 — CLI gang primitives:** `spawn-many`, `steer-all`, `kill-all`,
  `close-all`, `status --gang`, plus gang parentage in the manager-side
  spawn ledger (never `job.json` — see identity). Per-slug best-effort gang
  ops with aggregated failure reporting; `spawn-many` locks slugs in sorted
  order. **#9-gated:** steer-content operations (`steer-all`, and the P2
  coordinator relay) are blocked on the issue #9 answer — the prompt/steer
  funnel gains secret scanning (or an accepted risk note) before content
  relays land. `spawn-many` + `status --gang` themselves are not gated
  (they carry no relayed content).
- **P2 — coordinator job template:** a prompt template + example
  `prompt.md` showing a coordinator job using the client lib, with the
  per-leaf triage rule written into the template (no trusting leaf claims)
  and advisory-only attribution stated up front (P4 hardens it). **P2
  output is experimental: a coordinator template, not a trust story** —
  and P2 must answer open question 5 (which principals may drive the
  manager) before it is anything more.
- **P3 — shared-memory contract:** the gang PROGRESS.md format + the
  agent-immutable decision log (depends on issue #13's mechanism landing).
- **P4 — identity + audit:** per-job attribution in `watch` output and
  deploy audit lines — the advisory attribution P2 ships with hardened
  into audit; the OSS half of H10.

## Marketing gate

Honest copy today: "run one coding-agent job per box, orchestrated by you."
**Not** claimable until P2 lands: nothing new — P2 is the coordinator
template as an experiment.
**Claimable at P3:** "a lead agent coordinating parallel workers" — only
after the #13-dependent shared-memory contract lands, making the
coordinator's decision log agent-immutable against the leaves.
**Not** claimable until P4 + H10/H11: "multi-tenant teams with per-agent
attribution." Any launch/positioning copy that uses the word "team" or
"squad" must cite this doc's phase gate.

## Open questions

1. What is a sane default team size on the reference box (measure N=4/8/16
   worktree+tmux cost)?
2. Does the coordinator need a richer merge primitive than "merge each leaf
   branch in turn" (stacked-leaf workflows)?
3. Gang-wide budget accounting (`budget_hours` per leaf today; who pays for
   the coordinator's delegation turns?).
4. Interaction with issue #9: the prompt/steer funnel gets **no** secret
   scanning today — a coordinator job that relays operator input to leaves
   multiplies the funnel. Steer-content operations (`steer-all`, the P2
   coordinator relay) must not land before the #9 answer exists (secret
   scanning or an accepted risk note); `spawn-many` and `status --gang`
   themselves are not gated.
5. Which principals may drive the manager? A coordinator job running
   `muse-job/bin/muse-job` is an agent with spawn/steer/kill over sibling
   jobs — does P2 need a manager-side allowlist or role separation so a
   compromised leaf cannot fan out or kill the gang? The spawn ledger and
   gang destructive ops are built on this answer.
