# Box-side process shape gap analysis (#847 / #849)

**Date:** 2026-10-04. **Pinned to:** main `29ff48a` + the shipped
plane-worker checkout (no plane changes in this analysis).
**Question answered:** what is the box-side process landscape today, and
what is still unpinned about it?

## 1. Why this analysis exists

The phone-home gap analysis (`docs/PHONE_HOME_GAP_ANALYSIS.md`, G47.1)
deferred the box-side process-shape decision — one persistent `boxd` vs
something else — to the S5 box WSS client build:

> "That process shape (`boxd` or otherwise) is decided with the box WSS
> client (S5), not before."

S5 has since shipped (S5a connection core #959, S5b socket command
frames #976), and the box-side fleet has grown piece by piece — but **the
decision was never pinned**. Each slice picked the cheapest shape that
fit its own contract, and nobody ever wrote down the ensemble. This
analysis inventories what actually runs on a box today, names what's
unpinned or unsound about it, and files the fixes as slot-sized slices.

## 2. State: the five box-side processes

All five live in `pairing/spark_pair.py`, share one state dir
(`SVM_PAIR_DIR` or `~/.config/spark-pair`, 0700 — `_state_dir`,
L84), and are operator-installed (cron lines + one systemd unit,
documented in `pairing/README.md`). Nothing installs them
automatically — `deploy/` and `scripts/` contain no box-payload
installer (F-BD-6).

| # | Entrypoint | Shape | Schedule | Lock file | Log | State files |
|---|-----------|-------|----------|-----------|-----|-------------|
| 1 | `rotate --auto` (#846) | one-shot | hourly cron (README L150) | `.rotate.lock`, flock EX blocking (L542–552) | shell redirect to `/var/log/spark-rotate.log` | `enrollment.json` (0600) |
| 2 | `heartbeat` (#864) | one-shot | `* * * * *` cron (README L186) | `.heartbeat.lock`, flock EX blocking (L794–809) | `heartbeat.log` — failures only, append-only, **unbounded** (F-BD-3) | `last_heartbeat.json` |
| 3 | `ingest` (#874) | one-shot | `* * * * *` cron (README L259) | `.ingest.lock`, flock EX blocking held across the whole pass incl. cursor save (L1904–1912, save at L1843) | `ingest.log` — failures only, append-only, **unbounded** (F-BD-3) | `commands_cursor.json` `{cursor, epoch}` |
| 4 | `upload-filings` (#953) | one-shot | `* * * * *` cron (README L317) | `.upload-filings.lock`, flock EX blocking (L2219–2222) | `upload-filings.log` — failures only, append-only, **unbounded** (F-BD-3) | none (reads `confirm/pending/`) |
| 5 | `phone-home` (#959/#976) | **daemon** | supervisor, never cron (README L334) | `.phone-home.lock`, flock EX\|NB — singleton for the daemon's life (L3145–3155) | `phone_home.log` — lifecycle events only, append-only, logrotate `copytruncate` mentioned (README L360) | `phone_home_generation.json` (crash-safe increment per connect, L2267/L2584) |

Conventions that **did** converge (verified, not gaps):

- **Token rotation under a live socket is handled.** The daemon reads
  `enrollment.json` once at startup, but re-reads it on the
  `expired`-close path ("the rotate --auto cron may have replaced the
  token while we rode the old one"), with a one-rotate-per-session
  budget so a tight expired loop can't spin rotate→handshake→expired
  forever (`cmd_phone_home`, ~L3325–3360).
- **Heartbeat is the only liveness signal.** Pinned in the wire spec
  (S3, #941) and restated in the daemon's startup log line; the
  socket's existence is never treated as liveness.
- **Lock-file modes are 0600 everywhere**, forced with `fchmod` on
  every open (#883 pattern — a pre-existing lock file keeps its wider
  mode through `os.open`, so creation-mode alone is not enough).
- **The `.ingest.lock` discipline is shared by both ingest paths.**
  The cron ingest holds it blocking across the whole pass; the
  socket `approval_decision` path (#976) acquires it non-blocking and
  loudly drops the ack (→ DO re-drive) on contention, never wedging
  the daemon.

## 3. Findings

### F-BD-1 — the boxd end-state is unpinned (the G47.1 debt)

The current shape is emergent, not designed. Five processes, two
supervision models (cron vs systemd), four per-entrypoint locks, four
per-entrypoint logs — each slice chose its own conventions and no doc
says whether this is the steady state or a stepping stone to one
supervised `boxd`. G76.2 (filing-upload analysis) decided uploader
*placement* (periodic, separate cron line, "not folded into ingest")
but not the end state. Somebody has to say the word: **D19 pins it**
(see §4).

### F-BD-2 — the epoch bump races the cron ingest's cursor save

`_phone_home_bump_epoch` (L2637) rewrites `commands_cursor.json` —
the cron ingest's cursor file — **without holding `.ingest.lock`**.
The cron ingest holds that lock across its whole pass, including
`_save_ingest_cursor` (L1843). Interleaving loses the bump: cron reads
`(cursor, epoch=N)`, the daemon bumps to N+1, cron saves N back —
the reboot-equivalent incarnation fence never raises.

Blast radius today: **latent.** Plane-side stale-epoch enforcement is
still #848/#958 scope (not yet enforced), so no live command is
wrongly honored — but the fence is unsound by construction, and the
moment the plane starts enforcing epochs this becomes a real
incarnation-confusion bug. Reachable on both bump paths (generation
counter-loss and the stale-generation adopt path). **D20 pins the
fix** (filed as a p2 slice).

### F-BD-3 — the three cron failure logs are unbounded

`heartbeat.log`, `ingest.log`, `upload-filings.log` are append-only
via the shared `_fail` helper (L675) with no cap, no rotation, no
truncation. Success is quiet, so the growth rate is failure-driven —
but a sustained plane outage (or a 401 loop) writes three lines a
minute forever. Only `phone_home.log` has any rotation story at all
(logrotate `copytruncate`, README L360). **D21 pins the fix** (p3
slice): an in-code byte cap with single-generation rotation — no
logrotate dependency on the box.

### F-BD-4 — crash loops burn generations and reset backoff

Backoff `attempt` and the `rotate_tried` budget are in-memory only;
every daemon restart resets to the 1 s initial backoff, and every
connect claims a fresh generation (`_phone_home_claim_generation`,
L2584 — one file increment per loop iteration). A crash-looping box
burns generations and supersedes its own sessions at up to ~1 Hz.
Correctness survives (the DO's generation fence + command re-drive
handle it), but in-flight command acks churn and the S4b-4 journal
sink records connect churn. **D23** accepts this as a residual with
an optional p3 follow-up (persist the backoff attempt across
restarts).

### F-BD-5 — no cron stagger (unmeasured, presumably negligible)

All four one-shots are documented at `* * * * *` (README
L150/L186/L259/L317): four Python startups and four TLS handshakes at
the top of every minute. Nobody has measured the cost or the
plane-side burst shape; nobody decided it doesn't matter. **D22**
decides: leave unstaggered, document the inventory (D24) — staggering
is coordination debt for an unproven win.

### F-BD-6 — no unified operator surface, no installer

`docs/HOSTED_AUTH_OPERATOR_RUNBOOK.md` covers auth (pairing, rotation,
heartbeat). `pairing/README.md` documents each entrypoint. Nothing
covers the ensemble: which processes run, what each owns, how to
verify a healthy box, what to alert on. And nothing installs the
ensemble — no script writes the four cron lines or the systemd unit;
provisioning (#851, sub-slices #905–#908) covers the box, not the
agent payload that runs on it. **D24** files the checklist doc (p3);
the installer belongs to #906's scope (noted, not separately filed).

### F-BD-7 — the systemd unit contradicts its own comment [FIXED THIS TURN]

The README unit set `Restart=on-failure` (L348) while its comment
said "Exit 1 means HUMAN ATTENTION, not a restart loop … Alert on
repeated restarts instead of restarting forever" (L350–354). With
`Restart=on-failure`, systemd restarts on the deliberate exit-1
paths — a revoked token would restart-loop against a dead token until
the start limit trips. Fixed in this turn's diff:
`RestartPreventExitStatus=1` added, so exit 1 stays dead (the human
path) while crashes and signals still restart. Comment updated to say
exactly that.

## 4. Decisions

- **D19 — the mixed shape is the steady state; no boxd convergence.**
  The entrypoints have incompatible failure semantics (daemon exit 1
  = human attention, never restart; cron exit 1 = retry next minute)
  and different cadences. One supervised `boxd` would need an
  internal scheduler plus per-task failure budgets — more machinery,
  no operator demand. Extends G76.2's periodic-placement precedent
  to the whole ensemble.
- **D20 — the epoch bump joins the `.ingest.lock` discipline.**
  Non-blocking acquire; on contention, loud log + skip the bump —
  the DO's stale-generation close is the authoritative recovery
  (the code already says so at L2591–2594), the bump is advisory.
  Plus: the cron ingest re-reads `commands_cursor.json` under its
  held lock immediately before `_save_ingest_cursor`, closing the
  clobber in the common direction for one extra file read.
- **D21 — in-code log bounding for the cron failure logs.**
  1 MiB cap, single-generation rotation (`<log>.1`, then truncate),
  inside the shared `_fail` helper so all three logs get it at once.
  No logrotate dependency on the box. `phone_home.log` keeps its
  existing copytruncate story (lifecycle volume is already
  one-line-per-event).
- **D22 — cron stays unstaggered.** Document the four-timer inventory
  in the D24 checklist; revisit only with measurements.
- **D23 — crash-loop generation churn is an accepted residual.**
  Correctness is fence-handled; the journal records the churn for
  the operator to see. Optional p3 follow-up: persist the backoff
  attempt across restarts.
- **D24 — one operator checklist for the ensemble.** A new
  "Box-side ensemble" section in `pairing/README.md` (not a new
  doc): inventory table (process → schedule → lock → log → state
  files → failure semantics), install checklist, verification
  commands, alerting hooks. The box-payload installer itself stays
  in #906's scope.

## 5. Slices filed

All `track:hosted-product`, filed from this analysis:

- **#1019 (p2)** — epoch bump joins the `.ingest.lock` discipline
  (D20): non-blocking acquire in `_phone_home_bump_epoch`, loud
  skip on contention; cron ingest re-reads the cursor under its
  lock before saving. F-BD-2.
- **#1020 (p3)** — bounded cron failure logs (D21): 1 MiB cap +
  single-generation rotation in the shared `_fail` helper. F-BD-3.
- **#1021 (p3)** — box-side ensemble operator checklist (D24):
  the inventory + install + verify + alert section. F-BD-6.
- **#1022 (p3)** — cross-restart backoff persistence (D23
  follow-up): persist the backoff attempt so crash loops keep the
  60 s cap instead of resetting to 1 s. F-BD-4.

Not filed: the box-payload installer — belongs to #906
(claim→provision orchestrator); noted in F-BD-6.

## 6. Composition notes

- D20's ingest re-read touches `cmd_ingest`'s pass — coordinate with
  any in-flight ingest work (the #945 cross-process stamp lock
  slice shares the cursor file's neighborhood).
- D21's `_fail` change is the one shared helper the three cron
  entrypoints already share — one change, three logs.
- D24's checklist should cite the wire spec's liveness rule
  (heartbeat-only) so a future reader doesn't "fix" it by watching
  the socket.
- The F-BD-7 unit fix ships in this analysis's own PR (doc-only
  delta, reviewed with the doc).

## 7. In-turn fix (F-BD-7)

`pairing/README.md` phone-home systemd unit: added
`RestartPreventExitStatus=1` + a comment stating the semantics
(exit 1 = deliberate human-attention exit, never restarted; crashes
and signals still restart under `on-failure`). This is the only code
adjacent change in this turn; everything else is the analysis doc
plus the filed issues.
