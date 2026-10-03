# Action-approval records (plane-side)

The plane-side record for the hosted phone-approval flow (#849): an agent
action on a box → the owner taps approve/deny → the decision travels back
to the box. This document pins the **record** slice (#872, G49.1): what the
plane stores and the owner-authenticated endpoints that touch it.

Out of scope here (separate issues, separate endpoints):
- the box→plane filing leg that creates records from the box side (#876),
- the plane→box wire shape for decisions (#873),
- box-side ingest of decisions into confirmd (#874),
- the phone UX (rides #797/G23 push fan-out + #428 summons).

## Endpoints (all under `/v1/boxes/{box_id}`, all owner-key authenticated)

| Method & path | Purpose |
|---|---|
| `POST /approvals` | Create a pending approval record. Body: `{aid, summary, detail?, expires_in_secs?}`. Returns `201 {ok, approval}`. |
| `GET /approvals` | List records (`?status=pending|approved|denied|expired`, `?limit=`). Server-side expiry applied before listing. |
| `GET /approvals/{aid}` | One record. Server-side expiry applied. |
| `POST /approvals/{aid}/decision` | Record the decision. Body: `{decision: "approve"\|"deny"}`. Returns `200 {ok, approval}`. |

A box presenting its bearer token gets `401 "a box cannot decide its own
approvals"` on every one of these — a box can never decide (or read, or
create) its own approvals.

## The record

```jsonc
{
  "box_id": "box_7dccb3da",
  "aid": "deploy-prod-20261003-0629",   // client-chosen idempotency key
  "owner_id": "ok_9f31ab02",            // owner key that created the record
  "summary": "restart the production db",
  "detail": { "cmd": "restart", "svc": "db" },  // opaque, owner-authored
  "status": "pending",                 // pending|approved|denied|expired
  "decision": null,                    // "approve"|"deny" once decided
  "decision_seq": null,                // 1 on the first (only) decision
  "decided_by": null,                  // owner key that decided
  "decided_at": null,
  "created_at": 1790480000,
  "expires_at": 1790480600
}
```

- `aid` is chosen by the caller (1–64 chars, `[A-Za-z0-9._-]`). The
  `(box_id, aid)` primary key makes create retries safe: a retried
  create with the same `aid` returns the existing record (`200`,
  `deduped: true`) instead of a duplicate.
- `detail` is opaque to the plane (stored verbatim, returned parsed).
  4 KB cap.
- `owner_id` is the `#843` owner key that created the record. (#876's
  box-filing leg will add box-filed provenance as a forward migration.)

## Expiry: server-side only

- `expires_in_secs` defaults to 600 (10 min) and is clamped to [60, 3600].
  A client TTL is never trusted.
- A pending record past `expires_at` reads as `expired` — on get, list,
  and decide. Deciding an expired record is `410`; expiry is terminal,
  never a queue position.
- A **decided** record is terminal the other way: expiry never rewrites
  a decision. The decision happened inside the window; the audit trail
  stands.

## Decisions: write-once, idempotent

- The first decision wins (G49.2's approve-then-expire
  first-write-wins): the decide endpoint runs a conditional update that
  only transitions `pending` rows, so exactly one decider wins a race.
- Re-deciding with the **same** decision is a `200` replay
  (`deduped: true`) — double-tap and retry safe.
- A **conflicting** decision on a decided record is `409 "approval
  already decided"` — the owner creates a new approval instead of
  rewriting history.
- `decision_seq` is `1` on the decided record — the seam #873's wire
  shape (`box_id, aid, decision, decision_seq`) builds on.

## Limits

- `summary`: 1–256 chars. `aid`: 1–64 chars. `detail`: ≤ 4 KB JSON object.
- `expires_in_secs`: integer, clamped to 60–3600 (default 600).
- List `limit`: ≤ 200 (default 50).

## Error taxonomy

`401` no/invalid owner auth (or a box token — the explicit refusal above);
`404` unknown box or aid; `400` validation; `409` conflicting decision on
an already-decided record; `410` deciding an expired record.
