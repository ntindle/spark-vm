# muse-job

Wrapper + plugin that turns Muse Code on spark-vm into a delegatable
coding agent with the same interaction shape as subagents: async dispatch,
steer channel, question channel, introspection, lifecycle. No per-step
approvals — jobs run `muse --yolo` per standing owner authorization.

## Layout

| Path | What it is |
|---|---|
| `bin/muse-job` | CLI: `spawn/steer/status/list/log/kill/resume/close/watch`. Single-file Python, stdlib only. |
| `bin/muse-job-watchdog` | Deprecated ad-hoc watchdog script. NOT equivalent to `muse-job watch`: it emits a different finding set (blocked/question/stuck/over-budget vs the CLI's signal vocabulary) and the event-read hardening that landed in the CLI (session-uuid shape check, non-regular-file tamper refusal) was never ported to it. Use `muse-job watch`; this script stays only for manual ad-hoc runs. |
| `bin/muse-job-sweep` | Disk sweeper: prunes stale closed job dirs at >=85% disk; at >=93% closes the largest non-closed job (emergency breaker -- close, not kill: kill only ends the tmux session and frees ~0 bytes, the worktree is where the bytes are). Always JSON, fails open. |
| `bin/msp_host.py` | MSP serve-host client (issue #221, #228 plan): stdlib-only module that spawns/owns one `muse serve` per job, speaks NDJSON JSON-RPC 2.0 over stdio, runs the initialize/initialized handshake, correlates calls, dispatches notifications, routes server→client requests, and pins the schema fingerprint. Imported by `bin/muse-job` as the tmux replacement lands slice by slice. |
| `bin/msp_session.py` | MSP session-lifecycle client (issue #222, #228 plan): stdlib-only module on top of `msp_host.py` implementing `session/start`, `session/resume`, `session/list`, and `session/read` with client-side validation (UUIDv7 command ids, absolute workspace roots, the wire approval-mode enum, the 1..=200 list bound) and fail-loud result parsing, plus a smoke CLI. |
| `plugin/` | `muse-job` Muse plugin source (v0.3.1, user-scope, approved): `Stop` hook classifies turn ends (blocked/done/question/idle), `SessionEnd` hook, `PreLLMCall` session-UUID registry. Events land in `~/.local/share/muse-job/events/<uuid>.jsonl`. |
| `client/muse_job.py` | Python client presenting the subagent-like API (`spawn/steer/interrupt/status/list_jobs/log/wait_for_turn/pending_question/kill/resume/close`). Runs from the operator box over SSH. |
| `TOOL_INTERFACE.md` | Interaction map (subagents / browser tasks / exec / cron) and the Muse-Code-as-a-tool spec the client implements. |

## Deploy map (box)

| Repo path | Deployed to |
|---|---|
| `bin/muse-job` | `/home/ntindle/bin/muse-job` (on PATH) |
| `bin/muse-job-watchdog` | `/home/ntindle/bin/muse-job-watchdog` |
| `bin/muse-job-sweep` | `/home/ntindle/bin/muse-job-sweep` |
| `bin/msp_host.py` | `/home/ntindle/bin/msp_host.py` (to be imported by `bin/muse-job` as the #222–#227 cutover slices land) |
| `bin/msp_session.py` | `/home/ntindle/bin/msp_session.py` (session-lifecycle layer for the cutover; same import path) |
| `plugin/` | `/home/ntindle/muse-job-plugin/` (source) → user-scope plugin: `muse plugins install ./muse-job/plugin` (run from `~/spark-vm`), then `muse plugins approve` (`--force` on reinstall) |

Redeploy: copy the files over, then reinstall the plugin with `--force`
(plugin installs copy, not symlink).

## Job runtime

- One git worktree + branch per job under `/home/ntindle/muse-jobs/<slug>/`
- One tmux session `mjob-<slug>` running interactive `muse --yolo`
- Job prompt at `/home/ntindle/muse-jobs/<slug>/prompt.md`, progress in `PROGRESS.md`
- Job states (what `status`/`list` print): `active` / `blocked` — the watchdog acts on these (may page or attempt recovery); `killed` — operator-killed, the watchdog leaves it alone, `resume` is the deliberate way back; `closed` — archived, worktree removed, nothing to resume.

## Crons (operator box, not spark-vm)

- `muse-job watch` every 15m (via SSH): silent unless findings.
- `sparkvm-disk-sweeper` every 1h: runs `muse-job-sweep` via SSH, silent unless it pruned/closed.

## Event-file rotation

Hook event files (`~/.local/share/muse-job/events/<sid>.jsonl`) grow without
bound: the watch pass only ever scans the last 2 MB (a RAM/CPU DoS guard, not
a correctness mechanism). Each `muse-job watch` run owns rotation, not the
hooks and not the job agent (issue #27):

- **Trigger is size only**: when a job's event file passes 4 MB, the watch
  pass renames it to `<sid>.jsonl.<mtime-ns>.rot` and starts a fresh file.
  The agent cannot trigger rotation at will -- its only lever is appending
  lines, and rotation archives rather than deletes, so flooding to force a
  rotate buries nothing.
- **Atomic w.r.t. hook writes**: hooks append with `O_APPEND` by name on
  every event, so a hook that opened its file descriptor before the rename
  lands its line in the archive, and one that opens after lands in the fresh
  file. Every non-done line ends up in exactly one file -- never lost,
  never duplicated. (Done claims are intentionally present in both: the
  archive keeps them and the fresh file re-seeds them, so they keep paging
  fail-loud.)
- **Done claims survive**: terminal `done` lines are copied verbatim into
  the fresh file, so a rotated-out genuine `done` keeps paging every pass
  (a forged trailing `idle` still cannot bury a claim, per the Gotchas
  section below). A hook that wrote into the archive after the initial
  extraction is caught by a tail re-scan before the rotation completes.
  Malformed and non-done lines live on in the archive only.
- **Composes with the sweep**: rotated archives keep their original mtime,
  so `muse-job-sweep`'s 30-day prune ages them out like any old file (they
  never match an active job's skip name).

A rotation is reported as an `events-rotated` watch signal.

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
- `muse serve` (NDJSON JSON-RPC over stdio) is the planned job transport (#228): the 2026-09-17 `Not initialized` mystery was the missing `initialized` notification after `initialize` (verified 2026-09-21 against muse 1.3.0). `bin/msp_host.py` implements the transport + handshake (#221); tmux stays until the cutover slices land.
- `muse session-message send` fails for exec AND TUI sessions (`external_agent_ingress_closed`); steering is tmux-only.
