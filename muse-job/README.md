# muse-job

Wrapper + plugin that turns Muse Code on spark-vm into a delegatable
coding agent with the same interaction shape as subagents: async dispatch,
steer channel, question channel, introspection, lifecycle. No per-step
approvals — jobs run `muse --yolo` per standing owner authorization.

## Layout

| Path | What it is |
|---|---|
| `bin/muse-job` | CLI: `spawn/steer/status/list/log/kill/resume/close/watch`. Single-file Python, stdlib only. |
| `bin/muse-job-watchdog` | Watchdog pass script (also reachable as `muse-job watch`): emits JSON findings for blocked/question/stuck/over-budget jobs; silent when healthy. |
| `bin/muse-job-sweep` | Disk sweeper: prunes stale closed job dirs at >=85% disk; at >=93% kills the largest non-closed job (emergency breaker). Always JSON, fails open. |
| `plugin/` | `muse-job` Muse plugin source (v0.3.1, user-scope, approved): `Stop` hook classifies turn ends (blocked/done/question/idle), `SessionEnd` hook, `PreLLMCall` session-UUID registry. Events land in `~/.local/share/muse-job/events/<uuid>.jsonl`. |
| `client/muse_job.py` | Python client presenting the subagent-like API (`spawn/steer/interrupt/status/list_jobs/log/wait_for_turn/pending_question/kill/resume/close`). Runs from the operator box over SSH. |
| `TOOL_INTERFACE.md` | Interaction map (subagents / browser tasks / exec / cron) and the Muse-Code-as-a-tool spec the client implements. |

## Deploy map (box)

| Repo path | Deployed to |
|---|---|
| `bin/muse-job` | `/home/spark/bin/muse-job` (on PATH) |
| `bin/muse-job-watchdog` | `/home/spark/bin/muse-job-watchdog` |
| `bin/muse-job-sweep` | `/home/spark/bin/muse-job-sweep` |
| `plugin/` | `/home/spark/muse-job-plugin/` (source) → installed as user-scope plugin via `muse plugins install --force` + `approve` |

Redeploy: copy the files over, then reinstall the plugin with `--force`
(plugin installs copy, not symlink).

## Job runtime

- One git worktree + branch per job under `/home/spark/muse-jobs/<slug>/`
- One tmux session `mjob-<slug>` running interactive `muse --yolo`
- Job prompt at `/home/spark/muse-jobs/<slug>/prompt.md`, progress in `PROGRESS.md`

## Crons (operator box, not spark-vm)

- `muse-job-watchdog` every 15m: runs `muse-job watch` via SSH, silent unless findings.
- `sparkvm-disk-sweeper` every 1h: runs `muse-job-sweep` via SSH, silent unless it pruned/killed.

## Gotchas

- Turn-state events are **cooperative telemetry, not ground truth** (issue #3): the
  job agent runs as the same user with a full shell, so it can append fabricated
  `done` lines to its own event file. The hooks hardcode the event/sessions dirs
  (no env override -- an agent could otherwise blind the watchdog mid-session),
  whitelist the session id used in event/registration filenames, and never write
  through symlinks (a planted `events/<sid>.jsonl` symlink could otherwise make
  every hook append corrupt another job's state); hook-written text fields are
  ANSI/control-character sanitized. `muse-job watch` **never transitions a job
  to done on a hook event**: a `done` line is only ever a claim. `watch` scans
  the whole event file for the newest `done` (a forged trailing `idle` line
  cannot bury a claim), triages it against protocol checks (event names the
  job's recorded session uuid, cwd is at/under the job worktree, non-empty
  SUMMARY.md regular file present) and pages once per claim: `done-claimed`
  (checks passed) or `done-unverified` (checks failed; possible forgery). The
  dedup cursor lives in agent-writable job.json and is sanitized on read;
  after 3 done pages in 24h, claims coalesce into a single `done-repeated`
  page per window. `watch` also emits `events-missing` when the newest hook
  event is older than 30m (or none exists) while tmux is alive and a session
  uuid is recorded (event file deleted or hooks blinded) -- pages on EVERY watch pass while blind (fail loud; no dedup latch, since a latch in agent-writable job.json would be plantable)
  uuid -- and `events-tampered` when the event file is a symlink. A
  sophisticated agent can read this tooling and satisfy every check (including
  faking periodic heartbeat lines to defeat recency detection), so this verifies
  protocol compliance, not that the work happened -- genuine anchored trust needs
  agent-immutable sections (#13) or broker-held state, which this does not
  foreclose. The operator confirms SUMMARY.md, then `muse-job close`. `blocked`
  / `question` signals remain advisory.
- Never combine text+Enter in one `tmux send-keys` (silently no-ops vs the TUI); use separate text / sleep / Enter and verify the input box cleared.
- Spawn prompts via argv: `muse --yolo "$(cat prompt.md)"`.
- Muse's sqlite session index lags for TUI sessions; use the hook registry (`~/.local/share/muse-job/sessions/`).
- `muse serve` (JSON-RPC/MCP over stdio) was investigated as a cleaner transport; post-handshake calls return `Not initialized` (undocumented completion step). Deferred until tmux breaks.
- `muse session-message send` fails for exec AND TUI sessions (`external_agent_ingress_closed`); steering is tmux-only.
