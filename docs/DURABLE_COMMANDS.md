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
