# Push-subscription wire contract (#968 / GP2)

**Status.** Design contract, pinned to this repo at merge (PR number in
the CHANGELOG entry). Plane-side facts are pinned to the loop's
2026-10-12 reads of the `sparkvm-control` worker checkout — the plane
lives outside this repo, so the endpoints below are the contract the
plane must implement, not a description of what it does today.
Doc-first; honesty rules apply (`docs/POSITIONING.md`): everything
below is the **agreed design and the work to do**, not a promise.
Nothing here sends a push. "A push service with no subscriptions
pages nobody" — #968 fixes the registration half of the loop.

**Place in the slice plan** (`docs/HOSTED_PLANE_PUSH_GAP_ANALYSIS.md`
§3): GP2 of #849 (phone-approval loop). What shipped already: the D1
subscription store and custody (`docs/PUSH_SENDER_SCHEMA_CONTRACT.md`,
#988 — `push_subscriptions`, D3 keyed
`(owner_principal, box_id, device)`, D45 AES-256-GCM at-rest
encryption of `p256dh`/`auth`, D48c VAPID rotation discriminator),
the crypto (`hosted/push_crypto.py`, #967 S1), the send transport
(`hosted/push_sender.py`, #989, incl. the 410/404 → `tombstone`
taxonomy), and the dashboard's decide surface (`hosted/dashboard/`,
#954 — this doc's dashboard half extends #954's box-detail card, no
new page).

**Decision-number note.** The D-series is one global sequence; #988
continued it at D45. This doc continues at **D98** (the highest in-repo number is D97).

## 1. Endpoints

All endpoints are owner-auth per #843: `Authorization: Bearer
<owner-key>` (the box Bearer <redacted> no owner-key principal — 401). The
dashboard's existing `api()` helper already carries this header and
routes 401s to the sign-in view; the subscription UI reuses it.

### 1.1 `GET /v1/push/vapid-pubkey` → 200 `{ok, vapid_pubkey}`

The VAPID public key the browser needs as `applicationServerKey` in
`PushManager.subscribe()` (RFC 8292). `vapid_pubkey` is the
base64url-encoded raw 65-byte uncompressed P-256 point — the same
serialization `hosted/push_crypto.py` uses for `k` in the VAPID
`Authorization` header. Safe to expose: a public key is public; the
private half never leaves the plane (D3 custody; `push_crypto` S1
caveat stands). `vapid_key_id` rides the send path's D48c
discriminator — the UI does not need it and does not receive it.

**D102. The plane serves the reference service worker at `/sw.js`.**
`PushManager.subscribe()` requires a service-worker registration; the
plane serves `hosted/dashboard/sw.js` (this repo) at `/sw.js`, same
origin, scope `/`, from the plane bundle — redeploy the plane to pick
up dashboard changes. The worker is a
pure renderer — it shows the signed "go look" payload's summary
(`{aid, ttl_s, summary}`, D4) with `requireInteraction: true` and
opens `/` on tap; it holds no keys and sees no credentials. Any
future payload shape keeps the render-then-fallback rule (malformed
payload → generic page, never a crash).

(The D102 text previously claimed the served file was "byte-pinned
to the reviewed file" — downgraded #1476: the byte-pin had no
enforcement mechanism (same drift class as #1299), and the loop
cannot verify what the private plane serves. Pin enforcement, if
wanted, belongs to #1392's plane-side scope — a deploy-time hash of
the served file against the repo file, or serve-from-repo-at-deploy.)

### 1.2 `GET /v1/push/subscriptions?box_id=<id>` → 200 `{ok, subscriptions: [...]}`

Owner-scoped list of this box's subscription rows. Each entry carries
**display fields only** — never secrets:

```json
{ "device": "pixel-9",
  "status": "live",
  "last_page_at": "2026-10-12T19:31:02Z",
  "created_at": "2026-10-10T08:00:00Z" }
```

**D98. Secrets never travel on the read path.** The plane MUST NOT
return `endpoint`, `p256dh`, `auth` (or their nonces) on this
endpoint — they rest encrypted in D1 per D45 and are decrypted only
inside the send path. The dashboard UI needs the device label and the
status to render; returning more would hand the owner's ciphertexts
to every signed-in browser tab for no function. A `dead_410` row is
returned so the UI can tell "subscription died" from "never
subscribed" (the schema's #988 §1.3 note) — the tombstoned row's
secrets stay plane-side just the same.

`status` is the verbatim `push_subscriptions.status` value (`live` |
`dead_410`). `box_id` must belong to the owner principal (the same
ownership check #988's schema comment pins "enforced in code") —
404 for a box the owner does not own; an owner never learns whether
a foreign box id exists.

### 1.3 `POST /v1/push/subscriptions` → 201 created / 200 updated

Body (JSON):

```json
{ "box_id": "box-abc123",
  "device": "pixel-9",
  "endpoint": "https://fcm.googleapis.com/fcm/send/...",
  "keys": { "p256dh": "<base64url 65B uncompressed P-256 point>",
            "auth": "<base64url 16B secret>" } }
```

**D99. Validation (all 400, loud, before any write).**
- `box_id` owned by the caller (else 404).
- `device`: 1–64 chars, `[A-Za-z0-9._-]` — the aid charset precedent
  the #988 schema pins (so device names are URL-path-safe and
  DB-collation-safe).
- `endpoint`: `https://` only, no userinfo — the same discipline
  `hosted/push_sender.py` applies to send attempts (a cleartext or
  credential-bearing endpoint is a hard 400, not a warning).
- `keys.p256dh`: exactly 65 bytes raw, first byte `0x04`, and the
  point MUST pass the RFC 8291 §7 curve check (`push_crypto` already
  implements it — reuse it; an invalid peer key is a wasted row and
  a guaranteed dead-letter). `keys.auth`: exactly 16 bytes raw.
- Anything else in the body is ignored, not echoed (echoing
  attacker-controlled fields into a response is how stored-XSS in
  admin surfaces starts; the dashboard escapes everything anyway —
  `test_dashboard.py` pins the esc discipline).

The wire carries the *plaintext* key bytes because the plane must
re-encrypt them under its own D45 data key before writing (the
browser cannot know the plane's data key). The request runs over
owner-authenticated TLS; the plaintext exists in the plane's
request handler only for the duration of the write.

**D100. Upsert on the D3 key.** `(owner_principal, box_id, device)` is
the row identity (#988). A POST for an existing triple **replaces**
the row — fresh `endpoint`, fresh key material, `status` reset to
`'live'`, `added_by` = the owner-key id that made the call
(forensics, per the schema), `created_at` refreshed. The delete-then-
reinsert is one statement (`INSERT ... ON CONFLICT ... DO UPDATE`;
partial-column updates are a divergence class the table doesn't
need). This is also the 410 recovery path: the dead row's device
re-registers and comes back live — the dashboard offers it as
"Re-register this device" rather than "Subscribe" when it sees a
`dead_410` status.

**D101. Unsubscribe is a real delete.** `POST` never deletes; only
§1.4 does. Re-subscribe is therefore always a fresh row with fresh
key material (the #988 §1.1 note), and `dead_410` rows persist until
the owner either re-subscribes (D100 upsert) or deletes (§1.4) —
never silently garbage-collected by the write path.

### 1.4 `DELETE /v1/push/subscriptions/{box_id}/{device}` → 200 `{ok, deleted}`

Removes the `(owner_principal, box_id, device)` row outright (no
tombstone — the #988 §1.1 note: the `dead_410` status already serves
the "subscription died" distinction; an explicit unsubscribe is the
owner saying "never subscribed this device" again). 404 when no such
row exists for this owner (no existence oracle for foreign rows —
same rule as §1.2). `device`'s constrained charset makes it
URL-path-safe; the plane still validates the charset before lookup
(400 on a charset violation, never a lookup).

## 2. Client (dashboard) contract

The dashboard half is shipped in this repo
(`hosted/dashboard/dashboard.html`, #954's box-detail card gains a
"Push notifications" section; the committed inlined snapshot is
regenerated per the dashboard's sync ritual). The UI pins these
behaviors, which the contract requires of any conforming client:

1. **Capability gate.** `PushManager` subscription requires a service
   worker + push support. When unavailable, the section says why
   ("this browser can't receive push notifications") instead of a
   dead button — never a silently disabled control with no
   explanation.
2. **Register flow.** `PushManager.subscribe({userVisibleOnly: true,
   applicationServerKey: <vapid_pubkey from §1.1>})` → POST §1.3
   with the browser-minted endpoint and keys. A 201 and a 200 both
   read as success (idempotent re-register); 400 surfaces the
   plane's message verbatim (escaped); 401 routes to sign-in.
3. **Re-subscribe prompt.** A `dead_410` row renders a warning chip
   plus its own "Re-register" button carrying the row's exact device
   label — the 410 the send path classified as `tombstone` (#989)
   becomes a UI affordance, not a silent death. No auto-resubscribe:
   only the human re-arms the page channel.
4. **No-wipe guard.** Like the decide cards (#954): the 30 s
   auto-refresh never re-renders the section while a
   subscribe/unsubscribe is in flight or its feedback is on screen —
   the guard scopes the auto-refresh only. An explicit
   subscribe/unsubscribe completion reloads the section itself after
   a short read window (the 1.5 s delay the dashboard uses), which is
   the conforming behavior.
5. **The DOM never holds secrets.** The UI renders device labels and
   statuses only. The browser's own push keys (the `keys` it POSTs)
   are never written to `sessionStorage`, `localStorage`, or the DOM
   — they live in the PushManager's subscription object; the page
   holds the endpoint URL transiently for the POST and drops it.
6. **Unimplemented-plane degradation.** The wire contract ships
   before the plane endpoints exist (issue #1392). A 404 or 501 on
   the list endpoint renders a plain-language muted notice ("push
   notifications aren't enabled on this control plane yet"), never
   a raw error — the owner must not read a known not-yet state as a
   bug. 500s and network failures keep the error style.

## 3. What this does not claim

- The four plane endpoints are not implemented here — the plane is
  private. This contract plus `docs/PUSH_SENDER_SCHEMA_CONTRACT.md`
  is what a plane implementation must satisfy; the plane half is
  tracked as issue #1392 (conformance is a plane-side test task, not
  loop-executable against the private worker from the open repo).
  #968 stays open for that half.
- No email/SMS fallback: the "go look" payload discipline (D4)
  stands, and #428's §4 retirement still keys on the plane's
  `outcome='accepted'` record.
- Per-box opt-in vs per-owner default is still §5's open product
  question — rows exist only where the owner subscribed, so both
  policies fit this contract.
- The plane's in-worker send path keeps its existing rate shape
  (D10 bounds, #990 backpressure) — this contract adds writers of
  rows, not senders of pages.
