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
what it honors, and that decision is a security boundary:

- The executor honors an explicit allowlist of kinds (today: only
  `approval_decision`). Unknown kinds are **acked-and-logged**: the box
  must not execute what it does not understand, but it must not let one
  unknown kind wedge the queue either.
- A command the executor cannot execute safely is **not acked**, and the
  run stops at it: the cursor (highest *acked* seq) can never advance
  past an unacked command, so the command redelivers on the next pass.
- Malformed rows (no valid seq/kind/payload) are skipped loudly — there
  is no seq to ack and nothing safe to execute.
- Executor implementations must document their honored-kinds allowlist
  and their ack-and-log policy where operators can find it.

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

| `kind` | Producer | Payload | Owner |
|---|---|---|---|
| `approval_decision` | plane (#873) | `aid`, `decision`, `decision_seq`, `idempotency_key` | #849 |

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
