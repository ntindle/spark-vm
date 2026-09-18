# Tool interaction map → Muse Code tool spec

How the assistant's existing delegated tools actually communicate, and the
spec for Muse Code as a tool that works the same way. The adapter bridging
"how I want to use it" to "how it works today" is `~/workspace/bin/muse_job.py`.

## 1. How I interact with subagents today

| Aspect | Mechanism |
|---|---|
| Dispatch | `subagent.spawn(message=...)` — one text brief; the child inherits my full transcript, so the brief is short and points at shared context |
| Return | Immediate: an agent id. Fully async — I get the id back and move on |
| Response | **Pushed**: the runtime delivers the child's result into my context as a handoff when it finishes. I never poll |
| Steer mid-run | `subagent.send(id, message, interrupt?)` — queues a message, or interrupts current work first |
| Inspect | `subagent.list()` — every child: running/done/interrupted/failed, how long running, time since last activity |
| Lifecycle | `subagent.close(id)` stops it; `subagent.resume(id)` restarts an interrupted one |
| Questions | Subagents don't ask mid-run; they finish and report. If they need something they can't resolve, the result says so |

Key properties: async dispatch, pushed results, a steer channel, passive
introspection, explicit lifecycle.

## 2. How I interact with browser tasks today

| Aspect | Mechanism |
|---|---|
| Dispatch | `browser.spawn_task(...)` — returns a task id |
| Response | Handoffs on completion, like subagents |
| **Mid-run Q&A** | The task can **pause with `ask_for_information`** — a structured question (missing size/color, payment choice, "which of these?"). I answer through `browser.steer_task(task_id, ...)` and it resumes |
| Steer | `browser.steer_task` continues the task or answers its questions |
| Data filling | I pass known details up front (address, item, quantity); the task asks for what it can't resolve. Purchases add a formal review → explicit approval step before money moves |
| Interrupts | Steering a purchase flow is turn-based; the task waits at decision points |

This is the richer pattern: not just fire-and-forget, but a **question
channel** where the worker can ask and I can answer without killing it.

## 3. Other tools (for completeness)

- **exec / background procs**: sync or backgrounded; `process.poll/log/kill`. Results delivered on completion. No Q&A.
- **cron/hook workers**: fire-and-forget; results arrive as handoffs; I triage (surface / stay silent / fix the job).

## 4. The common shape

Every delegated tool I use follows this shape:

1. **Async dispatch** → handle immediately, result pushed later.
2. **Steer channel** → send input mid-run (queue, or interrupt-and-redirect).
3. **Question channel** → the worker can ask me things mid-run; I answer through the steer channel (browser's `ask_for_information` is the model citizen).
4. **Introspection** → status/list/log without disturbing the worker.
5. **Lifecycle** → kill / resume / close.

## 5. Spec: Muse Code as a tool with the same shape

```python
from muse_job import spawn, steer, interrupt, status, list_jobs, log, \
                      wait_for_turn, pending_question, kill, resume, close

job = spawn(slug, repo, prompt_file, budget_hours=8)
# -> {"slug", "session_uuid", "worktree"}  (async; session starts immediately)

steer(slug, "use tabs instead")
# -> {"delivered": True}  (queues if the agent is mid-turn, like subagent.send)

interrupt(slug)
# -> sends Ctrl-C to the agent's terminal (like subagent.send interrupt=True)

status(slug)
# -> {"job_state", "tmux_alive", "session_uuid", "session_status",
#     "bytes_total", "bytes_delta", "last_hook_event", "progress_age_s",
#     "dir_bytes", "elapsed_h", "budget_hours"}   (like subagent.list, scoped)

list_jobs()
# -> [{"slug", "state", "tmux_alive", "session_uuid", "elapsed_h"}]

log(slug, n=50)
# -> last n turn-end hook events (like reading a subagent's transcript tail)

event = wait_for_turn(slug, since_ts=None, timeout=3600, poll=15)
# -> the next turn-end hook event after since_ts, blocking with backoff.
#    This emulates the runtime's pushed handoff in a synchronous context.

q = pending_question(slug)
# -> None | {"kind": "blocked"|"question", "detail": "..."}
#    The ask_for_information equivalent: structured "the agent needs you".

kill(slug)    # stop the agent process tree (like subagent.close)
resume(slug)  # resume the recorded session in place (like subagent.resume)
close(slug)   # kill, remove worktree, delete branch, archive (terminal)
```

### How each maps to reality today

| Spec | Reality | Adapter note |
|---|---|---|
| `spawn` | `muse-job spawn` → tmux + `muse --yolo "$(cat prompt.md)"` | CLI already async-ish (returns after UUID discovery ~5s); library returns the dict |
| `steer` | tmux keystroke injection (separate text / Enter, verified) | encapsulated in `_steer`; fragility hidden behind `delivered` |
| `interrupt` | `tmux send-keys C-c` | new tiny addition |
| `status`/`list_jobs`/`log` | `muse-job status --json` / `list --json` / hook event files | direct JSON parsing |
| `wait_for_turn` | poll `~/.local/share/muse-job/events/<uuid>.jsonl` for a new record | the push-emulation; backoff 5s→60s |
| `pending_question` | hook classifier: `BLOCKED:` → blocked, trailing `?` → question | read latest event; the ask_for_information analog |
| `kill`/`resume`/`close` | `muse-job kill`/`resume`/`close` | direct |

### What the spec deliberately does NOT include

- **True push**: I can't receive socket push from the box; `wait_for_turn`
  polling plus the 15-minute watchdog cron (which pages me on
  blocked/question/stuck) covers it.
- **Structured approvals** (browser's purchase review): jobs run `--yolo`
  per the user's standing authorization; the only gate is the watchdog.
- **The `serve` stdio bridge**: investigated 2026-09-17 — `muse serve`
  speaks JSON-RPC/MCP over stdio and the initialize handshake answers, but
  post-handshake calls return `Not initialized`; the completion step is
  undocumented. Deferred again until the tmux transport actually breaks.

## 6. The question channel in practice

The agent protocol (in every prompt preamble):

- Genuinely blocked → append to `QUESTIONS.md`, end turn with `BLOCKED: <question>`
- Finished → write `SUMMARY.md`, end turn with `DONE: <summary>`
- Otherwise the hook classifies trailing-`?` as `question`

`pending_question()` surfaces both as `{"kind", "detail"}` — the exact
analog of answering a browser task's `ask_for_information` via steer:

```python
q = pending_question(slug)
if q:
    steer(slug, answer_for(q["detail"]))   # like browser.steer_task answers
```

The 15-minute watchdog cron runs `muse-job watch` and reports
blocked/question signals plus the completion/liveness set below; that is the
always-on version of this loop.

### Watch signal vocabulary (issue #3)

Hook turn-state events are **cooperative telemetry, not ground truth** -- the
job agent runs as the same user and can forge its own event lines. `watch`
never transitions a job to `done` on a hook event; a `done` line is only ever
a claim the operator must confirm (inspect SUMMARY.md, then `muse-job close`):

| signal | meaning |
|---|---|
| `done-claimed` | agent's `done` passed protocol triage (session uuid + worktree cwd + non-empty SUMMARY.md regular file). Verify, then close. |
| `done-unverified` | agent's `done` failed protocol triage. Possible forgery or broken hook payload. |
| `done-repeated` | 3+ done claims inside 24h; coalesced into one page per window (re-page backoff against pager fatigue). |
| `events-missing` | tmux alive, session uuid recorded, but the newest hook event is older than 30m (or none exists) -- event file deleted or hooks blinded. Pages on every watch pass while the condition holds (fail loud; no dedup latch, since a latch in agent-writable job.json would be plantable). |
| `events-tampered` | the session's event file is a symlink; the manager refuses to read through it (possible cross-job tampering). Pages on every watch pass while the condition holds (fail loud; no dedup latch, since a latch in agent-writable job.json would be plantable). |

Each claim pages once (deduped on the event ts against a read-sanitized
cursor in job.json); a newer `done` event pages again, up to 3 pages per 24h
window before coalescing. A sophisticated agent can satisfy every triage check
-- including faking periodic heartbeat lines to defeat the recency-based
`events-missing` -- so these verify protocol compliance, not that the work
happened.

### Derived layout is the canonical contract

`~/muse-jobs/<slug>/` holds `job.json`, `prompt.md`, `SUMMARY.md`,
`QUESTIONS.md`, `PROGRESS.md`, `work/` (the git worktree), and `tmp/`.
Pristine clones live directly under `~/repos/`; job branches are always
`job/<slug>`.

The manager **derives** the worktree (`<jobdir>/work`) and branch
(`job/<slug>`) from the slug for every destructive or security-relevant
operation (`close`, `resume`, the done-claim cwd check, the watch thrash
heuristic) instead of reading them from `job.json`, which the job agent
can rewrite (issue #11). A recorded value that diverges from the derived
layout fails closed with an explicit error -- divergence is treated as
tampering or an unsupported migration, never silently overridden. The one
value that cannot be derived (the pristine repo dir) is containment-checked
under `~/repos` **and** bound to the job by requiring the derived worktree
to be a registered worktree of that repo. Future layout migrations must
update the derivation, not the record.
