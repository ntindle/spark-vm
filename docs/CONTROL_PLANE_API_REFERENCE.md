# Control-plane API reference (sparkvm-control)

The consolidated HTTP reference for the spark-vm **control plane**
(`sparkvm-control`, the Worker that fronts an owner's fleet). It covers
every real endpoint across the owner, pairing, box, action-approval, and
durable-command namespaces — auth class, request/response shapes, and the failure codes.

**This doc adds no new claims.** Every section restates a contract that
already lives in a repo doc; the *Sources* section at the bottom names the
canonical doc for each namespace. For protocol nuance (cron lines,
incident response, clock-skew guidance), read the canonical doc, not this
reference.

**Applies to both planes.** The hosted plane (`https://api.sparkvm.dev/`)
and a self-hosted plane are the same endpoint contract — the dashboard
calls the plane that served it, and so does everything else here.

**Pinned:** main `36d353e9` (2026-10-03). The plane deploys from a
separate checkout — endpoint availability follows the plane's deploys,
not this doc. If this reference disagrees with the control-plane
checkout's `worker.py` module docstring (the endpoint table — the
source of truth), `worker.py` wins and this doc owes a fix-up turn.

## Auth classes

There are exactly two credential classes in separate namespaces, plus
the unauthenticated pairing flow. A box Bearer <redacted> presented at an
owner endpoint never matches; an owner key presented at a box endpoint
never matches.

| Class | Format | Where it rides | TTL |
|---|---|---|---|
| Owner API key | `svm_` + 43 urlsafe chars | `Authorization: Bearer <key>` | None — long-lived; rotate by mint + revoke |
| Box bearer token | opaque | `Authorization: Bearer <token>` | 24 h (`token_expires_at`); the previous token stays valid 15 min on heartbeats and `/rotate` after a rotation |
| None (pairing flow) | pairing code (8 chars, shown once) + ed25519 proof-of-possession | request/redeem bodies | Pairing code 15 min (lazy expiry on read); at most 50 pairings pending (429 beyond) |

The plane stores only SHA-256 hashes of all three secret classes
(`owner_keys.key_hash`, `boxes.token_hash`, `pairings.code_hash`). A box's
ed25519 keypair never leaves the box (public key only on the plane).

## Endpoints

### Owner endpoints (`/v1/owner/*`) — auth: owner key

| Method & path | Purpose | Request → response |
|---|---|---|
| `POST /v1/owner/bootstrap` | One-shot: mint the FIRST owner key, using a box token as the authority | `Authorization: Bearer <box-token>` (a token from an already-enrolled box) → `{ok: true, id, key}` **once**. After any active owner key exists: `403` with `"error": "bootstrap closed"`. There is no setup secret — a box-token holder bootstrapping *is* the owner. |
| `POST /v1/owner/keys` | Mint an additional owner key (#878) | JSON `{"name": "..."}` optional (1–64 chars; absent defaults to the key id) → `201 {id, key, warning}`, plaintext returned exactly once, never stored. A box token presented here 401s. |
| `GET /v1/owner/keys` | List owner keys | → key metadata (ids, names, created times) — never hashes, never plaintexts. |
| `DELETE /v1/owner/keys/{id}` | Revoke an owner key | The last-active-key guard lives *inside* the UPDATE, so concurrent revokes can't both pass — the plane always keeps at least one active owner key. `404` means unknown or already revoked. |

Fresh-database bootstrap is two-legged (the pairing first-claim path is
the usual one): on a fresh database with no owner keys yet, the very
first pairing approval is CLI-only (`spark_pair.py approve --bootstrap`) —
the dashboard can't sign in until that first owner key exists.

### Pairing endpoints (`/v1/pairing/*`) — enrollment, bounded human approval

The pairing-code enrollment flow (#844) that replaced the open
`POST /v1/boxes/register`. Box: `request` → human approves with the code
off the box screen → box polls `status` → `redeem` with an ed25519
proof-of-possession over the server-issued challenge.

| Method & path | Auth | Purpose |
|---|---|---|
| `POST /v1/pairing/request` | none | `{name, pubkey(b64), fingerprint}` → `{pairing_id, code, expires_at}` |
| `GET /v1/pairing` | owner | Pending/approved pairings (no code material) |
| `GET /v1/pairing/{id}` | owner | Detail incl. the **server-computed** fingerprint (the server computes it from the submitted pubkey itself — the client value is ignored, closing the fingerprint-spoof hole) |
| `POST /v1/pairing/{id}/approve` | owner | `{code}` typed by the human, compared out-of-band with the box screen |
| `GET /v1/pairing/{id}/status` | none | Box polls; `{challenge}` only when approved |
| `POST /v1/pairing/{id}/redeem` | none | `{signature(b64)}` over the challenge → `{box_id, token, token_expires_at}`; the first 24 h Bearer <redacted> issued |

### Box endpoints (`/v1/boxes/*`) — auth: box Bearer <redacted> unless noted

| Method & path | Purpose |
|---|---|
| `POST /v1/boxes/{id}/heartbeat` | Box liveness: JSON status body (`box_id`, `sent_at`, client, uptime, load, `token_expires_at`). The plane's own `200 {ok:true}` is the only "ok" — a missed heartbeat never fabricates one. Boxes with no heartbeat in 5 min are **STALE** on the dashboard; a never-heartbeated box shows "no heartbeat". (#864) |
| `POST /v1/boxes/token/rotate` | ed25519 proof-of-possession (`{"signature"}` in the body) rotates the box token: atomic self-referential swap, 24 h expiry, 15-min previous-token grace, null-signature MUST-reject. A `403` here means the Bearer <redacted> was accepted but the signature was rejected — check the box clock (±300 s window), don't re-pair. (#846) |
| `POST /v1/boxes/{id}/revoke` | **Owner key.** Stamps `revoked_at`; the box's Bearer <redacted> 401s *immediately* (heartbeats, rotation, bootstrap all refuse). Idempotent. One-way — the box comes back only by re-pairing. (#846) |

### Durable-command endpoints (`/v1/boxes/{box_id}/commands*`)

Owner-to-box command queue (#848). The plane is opaque to payloads — it
stores and delivers them; only the box executes them.

| Method & path | Auth | Purpose |
|---|---|---|
| `POST /v1/boxes/{box_id}/commands` | owner | Enqueue: payload ≤ 16 KB stored verbatim → `201 {ok, seq, epoch, state}`. Concurrent enqueues never fork the per-box sequence — a lost race gets `409 seq conflict` and the owner retries. |
| `GET /v1/boxes/{box_id}/commands/pending` | box token | Fetch due commands (current epoch, `seq > since`) → `{commands, acked_watermark, lease_secs}`. Cursors, seq lists, and epoch claims are range-checked (out-of-range → `400`); `limit` clamped to 200. Lease is 120 s: expired leases are re-offered, so delivery is at-least-once and the box dedupes by `(box_id, seq)` and **never treats delivery as execution** — execute, ack, then advance the cursor, where the cursor must be the highest *acked* seq, never the highest *fetched* seq. |
| `POST /v1/boxes/{box_id}/commands/ack` | box token | `{seqs:[...]}` — idempotent; acking only completes `pending`/`leased` commands; acking an `expired` (epoch-killed) command still returns success so the retry loop terminates. |
| `POST /v1/boxes/{box_id}/commands/epoch` | owner | Incarnation reset: bumps the box's command epoch and expires every pending/leased command of older epochs (they are never delivered again). A fetch may also claim a higher epoch (`?epoch=`); adoption is monotonic — a racing lower claim loses with `409 stale epoch`. |

### Action-approval record endpoints (`/v1/boxes/{box_id}/approvals*`) — auth: owner key

The plane-side record for the hosted phone-approval flow (#849, #872):
an agent action on a box → the owner taps approve/deny → the decision
travels back to the box. **Protocol published (#916, on main); plane
implementation is the next step** — the box→plane filing leg (#876),
the plane→box wire shape (#873), and box-side ingest into confirmd
(#874) are separate issues.

| Method & path | Purpose |
|---|---|
| `POST /v1/boxes/{box_id}/approvals` | Create a pending record. Body: `{aid, summary, detail?, expires_in_secs?}` (aid: client-chosen idempotency key, 1–64 chars; `(box_id, aid)` primary key — a retried create returns the existing record with `deduped: true`) → `201 {ok, approval}`. |
| `GET /v1/boxes/{box_id}/approvals` | List records (`?status=pending\|approved\|denied\|expired`, `?limit=` ≤ 200, default 50). Server-side expiry applied before listing. |
| `GET /v1/boxes/{box_id}/approvals/{aid}` | One record; server-side expiry applied. |
| `POST /v1/boxes/{box_id}/approvals/{aid}/decision` | Record the decision: `{decision: "approve"\|"deny"}` → `200 {ok, approval}`. First decision wins (conditional update on `pending` rows only); re-deciding with the same decision is a `200` replay (`deduped: true`); a conflicting decision on a decided record is `409 "approval already decided"`; deciding an expired record is `410` (expiry is terminal). |

A box token presented at any of these gets `401 "a box cannot decide
its own approvals"` — a box can never decide (or read, or create) its
own approvals. `expires_in_secs` defaults to 600 (10 min), clamped to
[60, 3600]; a client TTL is never trusted. Once decided, expiry never
rewrites the decision.

### Dashboard surface

| Method & path | Purpose |
|---|---|
| `GET /` | The authenticated fleet dashboard (`hosted/dashboard/` is the canonical copy, inlined into the deployed worker). Owner sign-in (key held in the tab's `sessionStorage` only); fleet list with STALE marking; box detail; pairing approvals; every API call carries the owner key as a `Bearer` token and a 401 anywhere returns the UI to the sign-in screen. |
| *(health)* | A public health check exists on the plane (`docs/PRODUCTION_DEPLOY_CONTRACT.md` live-verification checklist: "the plane answers on the public endpoint") but its path is not pinned in any repo doc — consult the control-plane checkout's `worker.py` module docstring. This row is a placeholder until a turn pins it. |

## Failure codes

| Code | Meaning on this plane | Operator action |
|---|---|---|
| 401 | Token dead (expired, revoked, never valid) | Re-pair the box (`request` + `redeem`); for an owner 401, check the key |
| 403 | Bearer <redacted> ok, proof-of-possession rejected (`rotate`) | Fix the box clock (±300 s window) and retry; do NOT re-pair |
| 403 `"bootstrap closed"` | An owner key already exists | Use the owner key; bootstrap is one-shot |
| 404 with JSON body | No such box / key id | Check the id; don't invent one |
| 404 without JSON body | Plane doesn't implement the endpoint | Update the plane (self-hosted) before concluding the box is missing |
| 409 `seq conflict` | Concurrent enqueue lost the sequence race | Retry the enqueue |
| 409 `stale epoch` | Fetch claimed a lower epoch than current | Adopt the current epoch; the older commands are expired |
| 429 | Pairing cap (50 pending) | Approve the real pairings or wait out the 15-min expiry |

## Deliberately NOT in this reference

- **`/fleet/*`** (G21, #795): a *design* for a read-only fleet API over the
  operator's local estate store (`docs/FLEET_READ_API_SPEC.md`) — different
  surface, different trust boundary (localhost-only, no auth in S1), not
  the control plane. Don't confuse the two.
- **Terminal streams / R2 uploads** (#853 → #919/#920/#921): spec'd and
  gap-analyzed, not implemented — no endpoints yet.
- **Approval-decision wire shape** (#873), **box-side approval ingest**
  (#874), **box→plane refusal filing** (#876): designed in the #849 gap
  analysis, not implemented.
- **Credential vending** (#850 → #890/#891): no vend endpoint, no box
  fetch path — the self-hosted swap-proxy half is the only half that
  exists.

## Sources (canonical docs per namespace)

- Owner bootstrap / owner keys / the credential inventory / failure-code
  semantics: `docs/HOSTED_AUTH_OPERATOR_RUNBOOK.md`
- Pairing flow, token rotation, heartbeat client contract, the endpoint
  table: `pairing/README.md`
- Durable-command queue, epochs, cursors, acks: `docs/DURABLE_COMMANDS.md`
- Action-approval records: `docs/APPROVALS_PLANE_PROTOCOL.md`
- Dashboard page, canonical-copy rule, sync: `hosted/dashboard/README.md`
- Production deploy posture for plane changes:
  `docs/PRODUCTION_DEPLOY_CONTRACT.md`

If an endpoint claim in this reference is wrong, file it against the
canonical doc above (the contract is wrong) or against this doc (the
restatement is wrong) — never silently edit both.
