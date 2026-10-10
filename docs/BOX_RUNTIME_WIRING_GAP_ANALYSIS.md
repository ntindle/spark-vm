# Box-runtime wiring gap analysis — the provisioned box's operational ensemble

Vision-vs-state of the provisioned box's runtime environment: what
`pairing/README.md` says must run on an enrolled box (the box-side
ensemble) versus what the golden image actually runs after the identity
hook enrolls it. Pinned to main `291e767` (2026-10-10) + the deployed
`deploy/golden-image/` tree at that commit.

Related: #851 (hosted provisioning), #847 (phone-home), #849 (approvals
loop), #1219 (scheduler/supervisor wiring build), #1220 (pairing-state
ownership), #907 (plane-attested pairing auto-approval), #1203
(identity-seed hook), #1205 (/data volume contract), #1021 (box-side
ensemble shape), #1020 (log bounding), #1022 (reconnect backoff).

## 1. Vision (what must run on an enrolled box)

`pairing/README.md` pins a five-process ensemble (`docs/BOXD_PROCESS_SHAPE_GAP_ANALYSIS.md` D19 — the five stay
separate by decision because their failure semantics are incompatible):

| # | Entrypoint | Schedule (vision) | Failure semantics |
|---|---|---|---|
| 1 | `spark-pair.py rotate --auto` | one-shot, hourly cron (`0 * * * *`) | exit 1 on any failure; cron retries next hour |
| 2 | `spark-pair.py heartbeat` | one-shot, every-minute cron (`* * * * *`) | exit 0 only on the plane's `{ok:true}`; every other outcome exits 1 |
| 3 | `spark-pair.py ingest` | one-shot, every-minute cron (`* * * * *`) | exit 0 only when every due command was consumed; transient failures are not acked |
| 4 | `spark-pair.py upload-filings` | one-shot, every-minute cron (`* * * * *`) | exit 0 only when every pending filing was uploaded/deduped/expired; a 401 aborts the pass |
| 5 | `spark-pair.py phone-home` | **daemon** under systemd — never cron | exit 0 = clean stop; exit 1 = human-attention (supervisor never restarts); exit 2 = crash (restarts under on-failure) |

Supporting prescriptions: the Install checklist (fresh box) installs the
four cron lines under the box-service user and the systemd unit for
phone-home; the Verification section defines a healthy box (`last_heartbeat.json`
fresh, failure logs silent, `systemctl is-active spark-phone-home.service`,
`token_expires_at` in the future); the Alerting hooks section pages on
repeated non-zero cron-tick exits and on the daemon's restart loop. Every
one-shot holds a blocking flock (EX) lock; the daemon holds a
non-blocking `.phone-home.lock` for its life. Timers are unstaggered by
decision (D22: three Python startups at the top of every minute, one hourly).
The phone-home unit is pinned as `Restart=on-failure` +
`RestartPreventExitStatus=1` + `RestartSec=5`.

## 2. Verified state (the golden image today)

- **No systemd.** `deploy/golden-image/supervisord.conf`'s own header:
  "Fly Machines run Docker images with an ephemeral rootfs — no systemd
  (FLY_DRIVER_RESEARCH.md F1). tini is PID 1 (ENTRYPOINT); supervisord
  owns the daemons."
- **No cron package.** The recipe's apt list is `ca-certificates curl git
  jq unzip sudo openssh-server supervisor tini unattended-upgrades`
  plus the XFCE/desktop stack, python3, node, gh (`deploy/golden-image/Dockerfile`
  L62–69) — no `cron`. The supervisord file's own cua-keepalive comment
  says "the image has no cron, so supervisord runs the same loop".
- **None of the five entrypoints is wired.** The supervisord config has
  programs for data-prep, identity-seed, sshd, swap-proxy,
  swap-inference, confirmd, push-worker, cred-ui, cua-stack, cua-bridge,
  cua-keepalive — and no program for `rotate`, `heartbeat`, `ingest`,
  `upload-filings`, or `phone-home`. Nothing else in `deploy/` or
  `harness/` references `spark-phone-home.service`. (#1219 verified this
  on 2026-10-09; re-verified unchanged at `291e767`.)
- **Identity-seed runs as root.** `[program:identity-seed]`, `user=root`,
  one-shot, priority 10; it enrolls into
  `SVM_PAIR_DIR` = `${HOME:-/root}/.config/spark-pair` unless the volume
  contract path is set (`deploy/golden-image/identity-seed-hook.sh`).
  The state dir is 0700 with 0600 `box.key`/`enrollment.json`.
- **Ownership is unsettled.** `docs/DATA_VOLUME_CONTRACT.md` pins the
  path `/data/pairing` but explicitly defers the owner: "Follows #1220
  (status quo: root; Options A/B named there — this contract does not
  pre-decide)"; the contract's own table (L154–155) says "#1219
  (scheduler wiring) + #1220 (pairing-state ownership): the
  `/data/pairing` path is pinned here; the owner is theirs to settle."
- **The Boundaries section names two gaps but not this one.**
  `deploy/golden-image/README.md` "Boundaries (honest, still open)"
  names redeem completion (#907's box-side half) and cold-stop state
  persistence (#1205) — not the scheduler/supervisor wiring. (#1219's
  body makes the same observation; it is re-stated here because it is
  the doc-read evidence for F-RW1/F-RW2 being live and unowned.)
- **The push-worker comment is precedent evidence.** The `[program:push-worker]`
  comment in `supervisord.conf` documents that the enrollment record
  "lives in the pairing user's home (identity-seed runs as root; redeem
  runs as the operator), which this swapd program cannot read" — i.e. the
  ownership choice already has live blast radius beyond the tick loops.

## 3. Findings (F-RW)

- **F-RW1 — the four one-shots are unwired on the provisioned path.**
  Re-verified unchanged at the pin (`291e767`) — #1219's consequence
  chain still holds: no heartbeat → the plane marks the box stale after
  300 s (fleet visibility dies); no `ingest` → the box never learns owner
  approve/deny/expire decisions over the durable channel (#874 / #876 S4
  chain is dead on the box); no `upload-filings` → box-side filing upload
  (#953) never runs; no `rotate --auto` → the 24 h box pairing token
  (#846) is never rotated, so the box 401s itself within a day. The
  provisioning lane ships enrollment, then goes silent.
- **F-RW2 — the phone-home daemon is unwired too.** Re-verified unchanged
  at the pin. The vision is explicit: "Run it under a supervisor, not
  cron." With no supervisord program, the WSS socket (#959 / #976) never
  connects on provisioned machines, so the S4b lane (#958) has no box
  side there. The five entrypoints' failure semantics are deliberately
  incompatible (D19), so the daemon cannot ride inside a tick loop.
- **F-RW3 — the pairing-state owner is undecided, and the wiring cannot
  be built without it.** #1220's Option A (state stays root-owned; ticks
  run as root — matches the hook; widens the trust boundary: root runs
  the box's plane client) vs Option B (a dedicated service user owns
  pairing state from first boot; the root hook enrolls then `chown`s; the
  ticks run as that user — matches the README's box-service DAC
  discipline). The same owner must run `redeem` (#907's box-side half),
  or the hook's `enrollment.json`-present idempotency check and redeem's
  `pairing.json` removal disagree on who may write the dir.
- **F-RW4 — the vision is systemd-shaped; the image has no systemd, and
  no translation exists.** *Genuinely new:* every operational prescription
  in the vision assumes systemd+cron: cron lines, the systemd unit, `systemctl
  is-active`, cron shell redirects to `/var/log/spark-*.log`, cron
  `MAILTO=`. None of these has a supervisord equivalent pinned anywhere.
- **F-RW5 — #1219 deliberately leaves the scheduler choice to the build
  ("cron package vs supervisord loops; either is fine"), but the choice
  has second-order consequences the build should not rediscover:**
  (a) the flock-lock contention profile changes under loop programs
  (blocking EX flock on a loop = serialize, not drop — README §"Lock
  file" was written for cron ticks); (b) log routing changes (see
  D-RW6); (c) interval-vs-wall-clock cadence changes (see D-RW4);
  (d) pre-redeem behavior is unspecified (see F-RW6). This doc pins the
  recommended resolution for each so the build starts from decisions,
  not rediscovery.
- **F-RW6 — pre-redeem tick behavior is unspecified.** *Genuinely new:*
  from first boot until the owner approves the pairing (a human step,
  #907's box-side half), any wired tick has no enrollment: heartbeat
  with no enrollment exits 1 every minute; phone-home with no token hits
  the human-attention path. Without an explicit skip policy the box is
  born paging — and a crash-looping tick loop under a supervisor looks
  like an outage to any fleet alerting built on F-RW7's contract.
- **F-RW7 — the Verification and Alerting-hooks sections are
  systemd-shaped and cannot be executed on the image.** *Genuinely new:*
  `systemctl is-active spark-phone-home.service` has no meaning where tini is PID
  1; "repeated non-zero exits on any cron tick" assumes cron + cron-mail
  or cron shell redirects; the daemon restart-loop alert assumes a
  systemd unit's restart accounting. The healthy-box contract needs a
  supervisord-shaped variant (D-RW7) — filed as its own build slice.
- **F-RW8 — cross-linked, not owned here: #1268.** The enrollment-record
  readability concern (the push-worker supervisord comment in §2: the
  enrollment record lives where the swapd-run worker cannot read it) is
  exactly #1268's filed subject ("golden image: push worker can't see
  the plane enrollment record", open p3, track:open-source, filed
  2026-10-10). The readability rule lives on #1268; this doc records the
  ownership-blast-radius evidence but does not re-own it.

## 4. Decisions (D-RW)

- **D-RW1 — scheduler mechanism: supervisord loop programs, not a cron
  install.** The cua-keepalive program in the same file is the proven
  precedent (`while true; do …; sleep 300; done`); the image is already
  committed to supervisord (no systemd, FLY F1); installing cron adds a
  second scheduler, a second failure domain, and a second log stream for
  five lines that supervisord already expresses. Honest provenance: #1219
  said "either is fine" — this decision goes one step further on the
  strength of the precedent + single-scheduler rationale; the build may
  still pick cron, but it must rebut the rationale, not ignore it.
- **D-RW2 — pairing-state owner: Option B — a dedicated service user
  owns `SVM_PAIR_DIR` from first boot; the root identity-seed hook
  chowns after enroll; all tick loops, phone-home, and redeem run as
  that user.** Rationale: the README's box-service DAC discipline is the
  settled rule for self-hosted boxes (ingest/upload-filings enforce it —
  Finding 50 in #953); the both-supported default means the image should
  not widen the trust boundary the self-hosted path refuses; the
  push-worker blind spot (F-RW8/#1268) shows the concrete cost of
  root-scoped state. This is a *recommendation* the #1220 build consumes,
  not a closed decision — the D-RW1-pattern escape applies: the #1220
  build may still pick Option A, but must rebut the DAC-discipline
  evidence and the F-RW8/#1268 blast-radius evidence rather than picking
  by default. The exact username is the build slice's; recommendation: a
  new dedicated user (not reusing `swapd` or `agent` — the plane client's
  trust tier differs from the proxy stack and the desktop stack). It
  connects to `DATA_VOLUME_CONTRACT.md` D-V1: the root data-prep one-shot
  lays out `/data/pairing` at first boot, and the hook's chown is what
  transfers that D-V1-laid dir to the service user.
- **D-RW3 — phone-home supervisord entry: `autorestart=unexpected` +
  `exitcodes=0,1`, `startsecs=5`, and the `startretries` accounting named.**
  The first two are the native supervisord translation of the unit's
  `Restart=on-failure` + `RestartPreventExitStatus=1`: exit 0 (clean stop)
  and exit 1 (human-attention — the daemon's exit 1 must never restart,
  notably `revoked` where re-pairing is the human path) are expected
  deaths; exit 2 (unexpected crash) and signal deaths restart. On the
  `RestartSec=5` line: supervisord has no direct restart-delay knob —
  `startsecs=5` carries over the cua-keepalive precedent (the program
  must stay up 5 s to count as started); restart pacing is supervisord's
  backoff, and after `startretries=3` quick crash-loops the program goes
  FATAL — a real delta from the unit's restart-forever, which D-RW7's
  supervisorctl check surfaces. The D19 incompatibility is preserved:
  the daemon is its own program, never folded into a tick loop.
- **D-RW4 — tick loop shape: one loop program per one-shot, with the
  supervisord settings pinned.**
  `while true; do /opt/sparkvm/pairing/spark_pair.py <tick>; sleep $((60 - $(date +%s) % 60)); done`
  (and `sleep $((3600 - $(date +%s) % 3600))` for the hourly `rotate`)
  under the D-RW2 user, with `autorestart=true` + `startsecs=5` per the
  cua-keepalive precedent. Three pins, each load-bearing:
  (a) no shell redirect — the outer logs are supervisord
  `stdout_logfile`s per D-RW6 (a `>>/var/log/…` redirect *and*
  `stdout_logfile` cannot own the same path; the file's own cua-keepalive
  precedent uses bare command + `stdout_logfile`);
  (b) the sleep is deadline-anchored to the wall-clock boundary, not a
  fixed 60 s — fixed sleeps drift by the tick's own runtime, so the three
  loops would wander relative to each other; the anchor preserves D22's
  "top of the minute" unstaggered decision (the hourly `rotate` anchor
  is equally fine against the 24 h token TTL — any hourly cadence keeps
  the token fresh);
  (c) `autorestart=true` (not the `unexpected` default) — under the
  default, a wrapper that exits 0 stays dead silently, and F-RW1's stakes
  are explicit: a dead rotate loop means the box 401s itself within a
  day. The blocking-EX flock discipline is unchanged (a slow plane still
  serializes rather than stacks).
- **D-RW5 — unenrolled-skip policy: wrapper-level, once-loud-then-quiet.**
  When `enrollment.json` is absent from the state dir, the loop wrapper
  logs one loud line naming the manual `redeem` step at wrapper start,
  then skips the client invocation and sleeps quietly each tick
  (per-tick loudness at 1/min would spam supervisord logs for the whole
  pre-redeem window). The phone-home wrapper follows the same gate but
  in daemon shape: it sleep-polls (with backoff) until `enrollment.json`
  exists, then execs the daemon — the D-RW3 exit-code mapping applies to
  the daemon proper, never to the pre-enrollment gate. (A bare
  daemon-as-program with an exit-1-on-unenrolled entry would compose
  into a program that exits 1 pre-redeem and — because exit 1 is an
  expected death under D-RW3 — never re-arms post-redeem.) Whether the
  client needs an explicit unenrolled exit code vs the wrapper owning the
  check is the build slice's call — the policy ("skip-quiet
  pre-enrollment, loud-once at start") is not.
- **D-RW6 — log routing: paths survive, the mechanism changes.** The
  outer tick logs keep their documented paths
  (`/var/log/spark-rotate.log`, `/var/log/spark-heartbeat.log`,
  `/var/log/spark-ingest.log`, `/var/log/spark-upload-filings.log`) via
  supervisord `stdout_logfile` (with the file's standard
  `10MB × 5` rotation) — replacing the cron shell redirect the alerting
  hooks reference. The in-code state-dir append-only logs
  (`heartbeat.log`, `ingest.log`, `upload-filings.log`,
  `phone_home.log`) are unchanged; the "steady growth in the state-dir
  logs = page trigger" hook survives verbatim. #1020 still owns the
  in-code bounding.
- **D-RW7 — the image gets its own healthy-box verification contract.**
  The pairing/README "Verification (healthy box)" section is
  systemd-shaped; the provisioned image needs the supervisord-shaped
  variant: all five programs RUNNING under `supervisorctl status`;
  `last_heartbeat.json` fresh; the state-dir failure logs silent; the
  last line of `phone_home.log` a normal lifecycle event; the
  `enrollment.json` `token_expires_at` in the future. Filed as its own
  build slice (new issue), not folded into #1219 — it is a doc/contract
  deliverable with its own acceptance bar.

## 5. Build slices

Filed by this turn (all `enhancement`, `track:hosted-product`):

- **#1273** (p2) — image healthy-box verification + alerting contract for
  the supervisord runtime (D-RW7). Delivers the supervisord-shaped
  Verification/Alerting-hooks contract; acceptance: the README checklist
  is executable on a provisioned box without systemd.
- **#1274** (p3) — unenrolled-skip policy for the provisioned-box tick
  loops (D-RW5). Delivers the wrapper-level once-loud-then-quiet gate
  (and the client-vs-wrapper decision); acceptance: a pre-redeem box
  ticks silently instead of paging.

Consumed by existing builds (pointer comments left on both —
#1219 id 6100515355, #1220 id 6100515521):

- **#1219** (scheduler wiring) — consumes D-RW1, D-RW3, D-RW4, D-RW5,
  D-RW6: the five supervisord programs, exit-code→restart mapping, loop
  shape, skip policy, and log routing. F-RW1/F-RW2's consequence chains
  are re-verified at this pin and stay the build's acceptance backdrop.
- **#1220** (pairing-state ownership) — consumes D-RW2 (recommendation +
  D-RW1-pattern escape hatch + D-V1 connection) and the F-RW8/#1268
  cross-link.

Explicit non-goals of this turn: the build itself (lives in #1219/#1220
plus the two new slices); the in-code log bound (#1020); the reconnect
backoff reset residual (#1022); the D22 stagger decision (restated, not
revisited). The enrollment-record readability concern belongs to #1268.
