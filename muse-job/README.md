# muse-job

Wrapper + plugin that turns Muse Code on spark-vm into a delegatable
coding agent with the same interaction shape as subagents: async dispatch,
steer channel, question channel, introspection, lifecycle. No per-step
approvals — jobs run `muse --yolo` per standing owner authorization.

## Layout

| Path | What it is |
|---|---|
| `bin/muse-job` | CLI: `spawn/steer/status/list/log/kill/resume/close/watch`. Single-file Python, stdlib only. |
| `bin/muse-job-sweep` | Disk sweeper: prunes stale closed job dirs at >=85% disk; at >=93% closes the largest non-closed job (emergency breaker -- close, not kill: kill only ends the tmux session and frees ~0 bytes, the worktree is where the bytes are). Always JSON, fails open. |
| `bin/msp_host.py` | MSP serve-host client (issue #221, #228): stdlib-only module that spawns/owns one `muse serve` per job, speaks NDJSON JSON-RPC 2.0 over stdio, runs the initialize/initialized handshake, correlates calls, dispatches notifications, routes server→client requests, and pins the schema fingerprint. Imported by `bin/muse-job` as the default transport (the #228 cutover has landed). |
| `bin/msp_session.py` | MSP session-lifecycle client (issue #222, #228): stdlib-only module on top of `msp_host.py` implementing `session/start`, `session/resume`, `session/list`, and `session/read` with client-side validation (UUIDv7 command ids, absolute workspace roots, the wire approval-mode enum, the 1..=200 list bound) and fail-loud result parsing, plus a smoke CLI. |
| `bin/msp_turn.py` | MSP turn-plane client (issue #223, #228): stdlib-only module on top of `msp_host.py` implementing `turn/start`, `turn/steer`, `turn/interrupt`, and `turn/cancel` -- the tmux send-keys replacement. Prompts travel as one opaque JSON string (never fragmented, never shell-parsed), and a server-reported not-live session surfaces as `TurnNotLiveError` instead of a silent success; dead-model recovery landed on issue #226. Ships a smoke CLI with an event-watch mode. |
| `bin/msp_view.py` | MSP view-plane client (issue #224, #228): stdlib-only module on top of `msp_host.py` implementing `view/subscribe` (replay `(after, head]` then live events) plus a job-state tracker mapping notifications to working / blocked (with the pending question surfaced) / idle / stalled -- the pane-scraping replacement `muse-job status`/`watch` read at the #227 cutover. Ships a smoke CLI. |
| `bin/msp_events.py` | MSP event-stream view layer (issue #224, #228): stdlib-only module that `muse-job`'s status/watch path actually reads — gapless replay from a per-job cursor, automatic re-seeding on dropped events, and the notification→job-state fold (working, blocked on approval or input, stalled, idle, turn failed). Hard-required by `bin/muse-job` (`_msp_imports`); supersedes `bin/msp_view.py` as the live view plane. |
| `bin/msp_recovery.py` | MSP dead-turn recovery ladder (issue #226, #228): stdlib-only module that climbs interrupt-the-zombie-turn → continuation re-anchored on the progress log → resume-fresh-session → page-the-operator when a job's model stream dies mid-turn. Hard-required by `bin/muse-job` (`_msp_imports`); the watchdog runs it automatically on stalled MSP jobs. |
| `plugin/` | `muse-job` Muse plugin source (v0.3.1, user-scope, approved): `Stop` hook classifies turn ends (blocked/done/question/idle), `SessionEnd` hook, `PreLLMCall` session-UUID registry. Events land in `~/.local/share/muse-job/events/<uuid>.jsonl`. |
| `client/muse_job.py` | Python client presenting the subagent-like API (`spawn/steer/interrupt/status/list_jobs/log/wait_for_turn/pending_question/kill/resume/close`). Runs from the operator box over SSH. |
| `TOOL_INTERFACE.md` | Interaction map (subagents / browser tasks / exec / cron) and the Muse-Code-as-a-tool spec the client implements. |

## Deploy map (box)

| Repo path | Deployed to |
|---|---|
| `bin/muse-job` | `/home/ntindle/bin/muse-job` (on PATH) |
| `bin/muse-job-sweep` | `/home/ntindle/bin/muse-job-sweep` |
| `bin/msp_host.py` | `/home/ntindle/bin/msp_host.py` (imported by `bin/muse-job`; the #228 cutover has landed) |
| `bin/msp_session.py` | `/home/ntindle/bin/msp_session.py` (session-lifecycle layer; same import path) |
| `bin/msp_turn.py` | `/home/ntindle/bin/msp_turn.py` (turn-steering layer; same import path) |
| `bin/msp_view.py` | `/home/ntindle/bin/msp_view.py` (view/liveness layer for the cutover; same import path) |
| `bin/msp_events.py` | `/home/ntindle/bin/msp_events.py` (event-stream view layer the status/watch path reads; hard-required; same import path) |
| `bin/msp_recovery.py` | `/home/ntindle/bin/msp_recovery.py` (dead-turn recovery ladder; hard-required; same import path) |
| `plugin/` | `/home/ntindle/muse-job-plugin/` (source) → user-scope plugin: `muse plugins install ./muse-job/plugin` (run from `~/spark-vm`), then `muse plugins approve` (`--force` on reinstall) |

Redeploy: copy the files over, then reinstall the plugin with `--force`
(plugin installs copy, not symlink).

## Job runtime

- One git worktree + branch per job under `/home/ntindle/muse-jobs/<slug>/`
- Default transport is MSP: one `muse serve` session per job (no tmux, no
  TUI scraping); `--tmux` opts back into the legacy path of one tmux
  session `mjob-<slug>` running interactive `muse --yolo`
- Job prompt at `/home/ntindle/muse-jobs/<slug>/prompt.md`, progress in `PROGRESS.md`
- Job states (what `status`/`list` print): `active` / `blocked` — the watchdog acts on these (may page or attempt recovery); `killed` — operator-killed, the watchdog leaves it alone, `resume` is the deliberate way back; `closed` — archived, worktree removed, nothing to resume.

### Detached per-turn supervisor (issue #1129)

`muse serve` has no detached-turn flag: a turn cannot outlive the serve
host that accepted it. The old spawn called `turn/start` and then
`host.close()`, SIGTERMing the turn before any model output — every MSP
spawn killed its own first turn by construction.

Every MSP turn now runs under a **detached supervisor** (the hidden
`_msp_supervise` subcommand): `spawn`/`steer`/`resume` fork it and return
as soon as the turn is live, and the supervisor holds the serve host
open until the turn reaches a terminal state. It owns the turn's
lifecycle. Supervisor state (pidfile, started record, heartbeat, view
snapshot, steer queue, prompt file, process log) lives in the operator-owned
metadata dir (`~/.local/share/muse-job/jobs/<slug>/supervisor/`), never
the agent-visible job dir — the #1145 treatment, so the agent has no
preamble-visible path to plant or rewrite it (same-user caveat: not a
privilege boundary against a determined shell user):

- **Poll + heartbeat** (`supervisor.heartbeat`, 120 s TTL) and a **view
  snapshot** (`supervisor.view.json`) — `status`/`log`/`watch` read the
  journal + snapshot instead of attaching a second host.
- **Steer queue** (`steer-queue.jsonl`, flock-guarded): `steer` appends a
  turn-tagged entry and returns; the supervisor drains the queue into
  the live turn (a steer queued for an older turn is dropped, never
  delivered to a later one).
- **Journal**: every poll/steer outcome is journaled as redacted signals.
- **Teardown**: SIGTERM/SIGINT set a stop flag so the `finally` always
  closes the host — no orphaned serve. A host that stays dead for 5
  consecutive polls exits the supervisor instead of livelocking it.
- **Files** (all under
  `~/.local/share/muse-job/jobs/<slug>/supervisor/` — the operator-owned
  metadata dir, never the agent-visible job dir):
  `supervisor.pid`, `supervisor.started.json` (the live
  `{"session_id", "turn_id"}`), `supervisor.heartbeat` (120 s TTL),
  `supervisor.view.json` (atomic tmp+rename snapshot),
  `steer-queue.jsonl` (flock-guarded), `supervisor.prompt.md`, and
  `msp-supervise.log` (the supervisor's stdout/stderr — the file a
  launch failure names with "see `<log>`").

User-visible output contracts (changed by this design):

- `spawn` prints `{"slug", "transport": "msp", "session_id", "turn_id",
  "state"}` — `turn_id` is new; `state` is the re-read job state (a
  stillborn first turn can already read `blocked`).
- `steer` on a live-supervised job prints `{"slug", "steer": "queued",
  "turn_id"}` — the message is queued, not delivered synchronously;
  `turn_id` names the turn it was queued against.
- `resume` on a supervised job prints `{"status": "supervisor-alive"}`
  instead of re-attaching.
- `status` may serve the supervisor's snapshot when the session is
  held: JSON gains `"snapshot": true` + `snapshot_age_s`; the text
  render prints a `snapshot: <age>s old (supervisor holds the session)`
  line so a stale turn id is never mistaken for a live poll.

Sessions are single-attach: while the supervisor holds a session,
`session/resume` from another host fails with `-32021 "already in
use"`. The read paths (`status`, `watch`) translate that into a
snapshot fallback instead of crashing; the recovery ladder is skipped
when the supervisor holds the session (it can't attach) and the
operator is paged to `steer`/`kill` instead. `kill` and `close` SIGTERM
the supervisor first — its teardown cancels the turn — then delete the
session as before.

### Stillborn first turns (issue #994, contract preserved)

The old spawn verified first-turn engagement before declaring success;
under the supervisor the spawn CLI is already gone when the turn's fate
is known, so the **supervisor** carries the contract: a first turn that
dies before engaging (cancelled/interrupted/unknown, never seen active)
is marked `blocked` with the `stillborn` record (`turn_id`, a
vocabulary-gated terminal label, the event-method journal) — never left
`active` in steady state (the spawn CLI may briefly print `active`
before the supervisor converges the state — see the output contracts
below). The watchdog's stillborn short-circuit pages on that record
with the two-path retry advice, exactly as before. A turn that
*completes* instantly is not stillborn: the done-claim path
(`SUMMARY.md`) owns that outcome. The engagement gate itself
(`begin_first_turn_watch` / `await_first_turn_engagement` in
`msp_turn.py`) remains as a tested library for any future caller that
needs a spawn-time liveness proof.

To retry a stillborn spawn, pick one path — the job dir cannot be both
removed and closed (removing the dir deletes the work tree, logs, and
diagnosis `close` would archive — the management record itself now lives
in the metadata dir, issue #11):

- New slug (keeps the diagnosis): `muse-job spawn <new-slug> --tmux`,
  then `muse-job close <slug>` the blocked job record — `close` archives
  it and removes the worktree and branch.
- Same slug: `muse-job close <slug>` first (this is what tears down the
  git worktree and deletes the job branch), then remove the job dir
  `/home/ntindle/muse-jobs/<slug>/` — `spawn` refuses a slug whose dir
  still exists — then `muse-job spawn <slug> --tmux`.

The legacy tmux transport is the safe retry: the first-turn cancellation
is a suspected MSP/serve-host race (session/branchChanged, per issue #994)
the `--tmux` path never hits. Note the retry advice below still names
`--tmux` for the *new* slug path — the old spawn error's wording is kept
verbatim so the watchdog's stillborn short-circuit and the spawn failure
stay consistent.

### TUI auto-update policy (issue #699)

**Updates are deferred while a job is active.** The `muse` launcher
stages a new versioned binary in the background at startup (hourly by
default) and a TUI that notices the staged update restarts itself
mid-turn -- the pane's foreground process name changing
(`muse-bin-1.3.0-R3233.1` -> `-R3401.1`) is what the watchdog's
`tui-updated` event detects (issue #212).

The launcher's own source gates the check+download on
`MUSE_NO_AUTO_UPDATE=1`; every TUI launch muse-job owns (`spawn`,
`resume`, and the resume-fallback relaunch) carries it in the launch
environment, so a job's process tree never stages an update. This is the
defer half of #212's deliberately-open policy question, now decided with
the switch confirmed in the launcher source rather than guessed.

- **Box updates still flow**: the var is per-process-tree, not per-box.
  The operator's own `muse` runs (and the installer/updater cron) stage
  updates at the normal cadence; job TUIs just don't participate.
- **Residual risk (honest)**: a concurrent same-user `muse` invocation can
  still stage an update into the shared install dir while a job runs, and
  the job's TUI can still bounce on it. The `tui-updated` watchdog event
  stays as the diagnostic for that case -- it is also the canary if a
  future launcher ever stops honoring the var.
- **Fail-loud prerequisite**: with the var set, a missing binary fails the
  launch ("installed binary is missing; rerun the installer") instead of
  self-healing. A box must have `muse` installed before the first job
  spawns (already true everywhere the updater runs); a spawn onto a
  binary-less box surfaces as a dead-TUI failure, the same class as any
  other launch failure today.

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
  (checks passed) or `done-unverified` (checks failed; possible forgery).
  After 3 done pages in 24h, claims coalesce into a single `done-repeated`
  page per window; the burst label is derived from the hook event file
  (the old record-side dedup latch was removed as demonstrably plantable,
  issue #3; the record itself moved to the manager-side metadata dir,
  issue #11). `watch` also emits `events-missing` when the newest hook
  event is older than 30m (or none exists) while tmux is alive and a session
  uuid is recorded (event file deleted or hooks blinded) -- pages on EVERY watch pass while blind (fail loud; no dedup latch, since a latch in the job record would be plantable)
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
- `muse serve` (NDJSON JSON-RPC over stdio) is the job transport (#228): the 2026-09-17 `Not initialized` mystery was the missing `initialized` notification after `initialize` (verified 2026-09-21 against muse 1.3.0). `bin/msp_host.py` implements the transport + handshake (#221). The tmux path remains as an explicit `--tmux` opt-in fallback.
- `muse session-message send` fails for exec AND TUI sessions (`external_agent_ingress_closed`); on the legacy `--tmux` path, steering is tmux keystroke injection only (the default MSP path steers via `turn/steer`).
