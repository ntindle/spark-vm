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
| `bin/muse-job` | `/home/ntindle/bin/muse-job` (on PATH) |
| `bin/muse-job-watchdog` | `/home/ntindle/bin/muse-job-watchdog` |
| `bin/muse-job-sweep` | `/home/ntindle/bin/muse-job-sweep` |
| `plugin/` | `/home/ntindle/muse-job-plugin/` (source) → installed as user-scope plugin via `muse plugins install --force` + `approve` |

Redeploy: copy the files over, then reinstall the plugin with `--force`
(plugin installs copy, not symlink).

## Job runtime

- One git worktree + branch per job under `/home/ntindle/muse-jobs/<slug>/`
- One tmux session `mjob-<slug>` running interactive `muse --yolo`
- Job prompt at `/home/ntindle/muse-jobs/<slug>/prompt.md`, progress in `PROGRESS.md`

## Crons (operator box, not spark-vm)

- `muse-job-watchdog` every 15m: runs `muse-job watch` via SSH, silent unless findings.
- `sparkvm-disk-sweeper` every 1h: runs `muse-job-sweep` via SSH, silent unless it pruned/killed.

## Gotchas

- Never combine text+Enter in one `tmux send-keys` (silently no-ops vs the TUI); use separate text / sleep / Enter and verify the input box cleared.
- Spawn prompts via argv: `muse --yolo "$(cat prompt.md)"`.
- Muse's sqlite session index lags for TUI sessions; use the hook registry (`~/.local/share/muse-job/sessions/`).
- `muse serve` (JSON-RPC/MCP over stdio) was investigated as a cleaner transport; post-handshake calls return `Not initialized` (undocumented completion step). Deferred until tmux breaks.
- `muse session-message send` fails for exec AND TUI sessions (`external_agent_ingress_closed`); steering is tmux-only.
