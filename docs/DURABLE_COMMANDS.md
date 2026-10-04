# Durable commands (queue, acks, leases, epochs)

Owner-to-box command queue on the control plane. The plane is opaque to
payloads — it stores and delivers them; only the box executes them.

## Endpoints (all under `/v1/boxes/{box_id}`)

| Method & path | Auth | Purpose |
|---|---|---|
| `POST /commands` | owner key | Enqueue a command. Returns `201 {ok, seq, epoch, state}`. |
| `GET /commands/pending` | box Bearer <redacted> | Fetch due commands (current epoch, `seq > since`). Returns `{commands, acked_watermark, lease_secs}`. |
| `POST /commands/ack` | box Bearer <redacted> | Acknowledge executed commands (`{seqs:[...]}`). Idempotent; unknown seqs are reported. |
| `POST /commands/epoch` | owner key | Reset the box's command epoch (incarnation reset). Kills in-flight commands of older epochs. |

## Sequence numbers

- Per box, monotonically increasing, assigned by the plane at enqueue.
  Concurrent enqueues never fork the sequence: a lost race gets `409 seq conflict` and the owner retries.
- A command's identity is `(box_id, seq)` — never reused.

## Epochs (box incarnations)

- The epoch tracks the box's *command incarnation*, not its network
  session: reboot, reprovision, or counter loss bumps it; a plain
  transport reconnect does **not**.
- A fetch may claim a higher epoch (`?epoch=`). Adoption is monotonic —
  a racing lower claim loses (`409 stale epoch`) rather than regressing.
- The box-side ingest always attaches its current claim:
  `GET /commands/pending?since=…&limit=…&epoch=<n>` (#947). The param is
  omitted when the box has no epoch yet (first run) so a fresh box never
  asserts a bogus `epoch=0`. Stale-epoch detection on the plane is
  #848/#958 scope; the box only ever asserts what it knows.
- Claiming a new incarnation expires every pending/leased command of
  older epochs: they are never delivered again. An owner epoch reset
  does the same for recovery (e.g. a box that lost its counter).

## Delivery semantics: at-least-once

- Fetch returns due commands and stamps each with a short lease
  (`lease_secs`, currently 120). Expired leases are re-offered on the
  next fetch — a crashed box redelivers instead of losing commands.
- The same command may therefore be delivered more than once. The box
  dedupes by `(box_id, seq)` and must **never** treat delivery as
  execution: execute, ack, then advance the cursor.

## The cursor contract

The box's `since` cursor **must be the highest *acked* seq, never the
highest *fetched* seq**. Advancing on fetch silently skips redelivery:
a command fetched but not yet acked (lease expired) has a seq at or
below the highest fetched seq, so `seq > since` would hide it forever.
The fetch response includes `acked_watermark` (the plane's max acked
seq) so the box can reconcile its cursor after a restart.

## Acknowledgement

- Acking is idempotent: acking an already-acked command succeeds (the
  at-least-once executor may redeliver).
- Acking only completes `pending`/`leased` commands. Commands killed by
  an epoch transition (`expired`) keep their audit trail and can never
  be delivered again — but acking them still returns success so the
  box's retry loop terminates.

## Box executor policy (reference implementation: `spark-pair.py ingest`, #874)

The plane is opaque to payloads and kinds — the *box executor* decides
what it honors, and that decision is a security boundary. Stated
plainly: the ingest promotes the plane from relay to **grant-issuing
authority** — a compromised plane can mint arbitrary local grants
through the approve path. That is the feature's purpose (the owner's
tap moved to the plane dashboard), not an accident: the box already
trusts the plane for pairing, token rotation, and liveness, and
approvals now join that trust set.

Command outcomes come in three classes — the executor must
distinguish them, because confusing them either wedges the queue or
hides a dropped decision:

- **Transient (not acked, run stops):** the command may succeed on a
  later tick — local I/O failed, the grant writer failed, the grant
  window is live but the mint did not complete. The cursor (highest
  *acked* seq) can never advance past an unacked command, so the
  command redelivers on the next pass.
- **Permanently unprocessable (acked-and-logged loudly, run exits
  1):** the command can never succeed for this client — e.g. a
  tenant-scoped item on a pre-H10 box, or a decision for an aid the
  box never filed. Acking advances the queue past it (no wedge), but
  the loud log + exit code flag the operator: a decision was dropped
  on the floor and only an upgraded client can recover it.
- **Plane bugs (reference implementation: acked-and-logged, no
  stamp):** malformed payloads are never executed. Unknown kinds —
  kinds with no row in the registry below — are acked-and-logged by
  the reference implementation: the box must not execute what it does
  not understand, and a single unknown kind must not wedge the queue
  behind a version skew. But note the version-skew hazard: the box
  *silently skips the semantics*, not just the execution. Ack-and-log
  is therefore a **reference-implementation liveness choice, not a
  universal security policy**: the kind registry declares per-kind
  behavior, and any kind with security effects (grant revocation,
  kill-switches, future authorization verbs) MUST declare fail-closed
  handling (not acked, run stops loudly) — an old client that does not
  know a security-effect kind must never silently skip it. The plane
  owns the registry: it must not enqueue a kind for a box whose
  executor does not list it (plane-side gating; future hook — until it
  lands, the dead-letter hook below is the designed backpressure
  answer, and the ack-and-log stays operator-visible via the loud log
  + exit code).
- Executor implementations must document their honored-kinds allowlist
  and their ack-and-log policy where operators can find it.

### Residual race posture (cross-process answer writers)

The ingest is the first cross-process answer writer: it does not hold
confirmd's per-aid lock (in-process only). The mitigations are
write-if-absent O_EXCL stamping (first writer wins among stampers),
the approve path's pre- and post-mint terminal re-checks, and the
grant-writer's approval-id dedupe. The residual: a near-simultaneous
contradictory owner tap on both surfaces can last-writer-win through
the local path's clobbering `os.replace` — e.g. plane-approve mints a
live grant, then a local deny overwrites `consumed/` → live grant +
denial-suppressed tuple for up to the grant TTL. Both decisions are
owner-authentic, the window is tiny, and there is no non-owner
injection — but the two surfaces can disagree, and the grant outlives
the denial. The structural fix (a cross-process stamp lock shared by
`_answer_locked`, both reapers, and the ingest — and/or a
per-approval-id grant revoke) is tracked in #945; until it lands,
the post-mint race journals loudly with the `grant-writer revoke
--job` runbook instead of failing silently.

## Limits

- Payloads ≤ 16 KB, stored verbatim, never executed by the plane.
- `limit` is clamped to 200 commands per fetch.
- Cursors, seq lists, and epoch claims are range-checked; out-of-range
  input is rejected with `400`, never a server error.

## Future hooks (pinned, not yet implemented)

- `deliveries` (lease-stamp count, returned per command) is the future
  dead-letter hook: repeatedly expiring commands can be moved to a
  `dead` state, skipped by fetch, and surfaced to the owner.
- The same table/seq/epoch semantics are transport-agnostic: when the
  box's persistent command channel lands, it drives off this queue.

## Command kinds

The plane is opaque to payloads and kinds — except for the kinds it
produces itself. This registry pins the plane-produced kinds; a new
plane-produced kind needs a row here before the plane may enqueue it.

| `kind` | Producer | Payload | Owner | Unknown-client behavior |
|---|---|---|---|---|
| `approval_decision` | plane (#873) | `aid`, `decision`, `decision_seq`, `idempotency_key` | #849 | n/a (honored kind) |

### `approval_decision` (#873, #849)

The first honored kind — the plane is a command *producer* here, not
just a store. Enqueued when an owner decision lands
(`POST /v1/boxes/{id}/approvals/{aid}/decision`) and when a pending
approval expires server-side. The box learns of decisions *only*
through this command: it cannot read approvals itself (#872).

Payload (all required):

```json
{
  "aid": "<approval id>",
  "decision": "approve|deny|expire",
  "decision_seq": 1,
  "idempotency_key": "approval_decision:<box_id>:<aid>:1"
}
```

- `decision`: `approve` or `deny` from the owner's tap; `expire` when
  the approval's window passes with no decision. A `deny` is terminal
  for the parked task (mirrors the box-local `denied:<aid>` leg in
  `docs/APPROVAL_CLIENT_SIGNAL.md`); `expire` mirrors `expired:<aid>`.
- `decision_seq`: per-approval decision sequence. Always `1` today —
  the approval record is write-once (approve-then-expire races resolve
  first-write-wins), so an approval produces at most one decision
  command. Reserved for future multi-decision flows.
- `idempotency_key`: `approval_decision:<box_id>:<aid>:<decision_seq>`.
  The box dedupes on this key (#874): redelivery after a crashed box
  re-delivers the *same* decision, never a contradictory one. A
  *sequential* replayed owner tap never double-enqueues (the plane
  checks for an existing command with this key before enqueueing);
  two *concurrent* replays can both miss the check and enqueue
  distinct seqs with the same key — the box-side key dedupe is the
  backstop, and the payloads are identical.
- `box_id` is not in the payload: it rides the command row's `box_id`
  column (and is embedded in the key). Both carriers (the per-box
  HTTPS pending endpoint, the per-box socket) are box-scoped, so the
  box never needs it in the payload.

Exactly-once enqueue (sequential): the decision record's write-once UPDATE is the
gate — only the winning decider enqueues; idempotent replays find the
existing command and enqueue nothing. Server-side expiry uses a
per-aid conditional UPDATE for the same guarantee: a raced expiry
transitions the row once, so at most one `expire` command per aid.

**Mode split (self-hosted vs vend):** the reference executor's approve
path shells to `proxy/grant-writer`, which records a grant against the
box's **local secrets dir** — this is the self-hosted mode, and it is
the only mode the reference implementation supports. On a vend-mode
box (#891: RAM-only, plane-vended short-lived credentials, "no real
secret material on the box filesystem" per #850) the ingest would mint
a grant authorizing nothing usable (swap fails closed on the unknown
credential) — worse, the box would hold two divergent authorization
artifacts for one owner decision (local grant at the default TTL +
vended lease at minutes-to-hours TTL). **Vend-mode boxes must not run
the local-mint approve path**; the dual-mode seam (config-time source
selection) is tracked in #948 (within #891's scope). Until it lands,
approve→local-mint is documented as self-hosted-only, not as
mode-independent reference behavior.
