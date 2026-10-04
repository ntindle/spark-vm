# hosted — the hosted control plane's tenant layer (S1)

`GET /tenant/status`: the machine-readable onboarding status that the tenant
Muse (linked ed25519 key, signed requests) and the signup page (magic-link
session cookie) poll during the first-ten-minutes onboarding arc.

The full contract is `docs/TENANT_STATUS_ENDPOINT.md`. What this component
implements (G3 implementation slice S1):

- the 13-code §2 machine vocabulary, exactly spelled, with the operator-only
  codes (`policy-misfire`, `no-gated-action`) carrying no `human_key`;
- the §2 transition rules 1–8 (no backwards moves; the relay/cert suspension
  latch; the maintenance latch; the rule-7 session-restart carve-outs) as a
  tested event→transition mapping over per-box arc records;
- the JSON tenant-record store, with the `approvals_url` carrier minted once
  at signup stage 2 (write-if-absent + re-read, linearizable across processes
  via an `flock`'d lock — exactly one minter wins a concurrent stage-2 race;
  funnel re-entry is a read path; rotation only via an explicit operator
  event), and the §8 empty-candidate hold (when the leading box is deleted
  pre-`live`, the endpoint holds the last reported code with `detail` noting
  the operator event);
- the endpoint itself: two-sided auth, 401 when the caller's identity can't
  be established, 404 for valid credentials with no servable record (deleted
  or pre-stage-2), `Cache-Control: no-store`, and GET never changes state.

Run the tests: `python3 -m pytest hosted/` from the repo root.
Run the daemon: `python3 -m hosted.tenant_status --store /path/tenants.json`
(signed-request verification is wired by the control plane at deploy time —
the daemon refuses signed requests until then rather than trusting them).

Deliberately stdlib-only, so the module runs unchanged on the self-hosted
box, the hosted control plane, and the operator laptop. The ed25519 verify
primitive is injected (stdlib has no ed25519) — the endpoint never trusts
an unverified signature.

Slice boundaries: S2 wires the H4 driver's `BoxStatus` into the tenant
layer (the `live`-entry AND-combine is the `live_entry_ready` unit); S3
wires the readers (signup page meta-refresh, Muse poller).

## relay_liveness.py — the relay session-liveness journal (R1)

The passive liveness instrument from `docs/RELAY_LIVENESS_DESIGN.md`:
the relay daemon emits one §2 session frame per tenant↔VM SSH session
to a bounded local JSONL journal, and the control plane asks
`relay_session_liveness(vm_id)` → `{session_id, state, last_bytes_at,
hostkey_verified}` where state is `active` (bytes within the last
5 minutes), `idle` (no bytes for over 5 minutes), or `closed` (the
session ended with a §2 cause).

Frames are metadata only — timing and counters, never payload; the
schema validator rejects any non-§2 field. Rotation is the journal's
own contract: the journal plus at most 3 rotated generations are
capped by a byte bound (worst case 4 × (64 MiB + one row)), so total
on-disk footprint is bounded regardless of session volume. The bound
is bytes, not rows — stated plainly so no reader assumes a row count
the code doesn't enforce. The prober identity marker (R2's
discriminator) is enforced at the journal: prober-marked frames are
dropped, never journaled. Unknown boxes return no data — darkness is
insufficient-observability, never an `ok` (a missing journal directory
is darkness too, not an error; only the writer fails loud).

Run the tests: `python3 -m pytest hosted/` from the repo root.
Query smoke test: `python3 hosted/relay_liveness.py --query <vm-id>
[--journal /path/journal.jsonl]`.

## push_crypto.py — Web Push content-encoding crypto (RFC 8291), stdlib-only

The design-hypothesis validation for #967 S1 (the plane Web Push sender):
proves the Python plane worker can do in-worker Web Push sending with no
JS interop and no C extensions. Implements ECDH P-256, HKDF-SHA-256,
AES-128-GCM, and RFC 6979 deterministic ECDSA (for VAPID JWTs, RFC 8292)
in pure Python, and pins every step against the RFC 8291 section 5 /
Appendix A worked example in `test_push_crypto.py` (22 tests).

Result: validated — one full send (ephemeral keygen + ECDH + KDF +
AES-GCM + VAPID sign, 200 B payload) costs ~38 ms on the loop's dev VM,
so S1 proceeds in-worker. Read the module docstring before reusing: the
field arithmetic is not constant-time (assessed non-exploitable in the
plane's threat model), peer keys are curve-validated per RFC 8291
section 7, and the VAPID private key must never leave the plane.

## push_payload.py — push payload construction discipline (#970 / GP4)

The plane's push path is a hostile-*box* surface: box-controlled strings
flow into payloads the plane signs and sends to the owner's lock screen.
This module pins the single construction-time rule the future sender's
enqueue boundary applies to every box-controlled payload field —
control-character strip (C0 + C1, so ANSI escapes die) plus an explicit
byte-length bound with ellipsis truncation that never splits a code
point — proven by `test_push_payload.py` (22 tests, neutering-verified
non-vacuous). Payload shape is exactly `{aid, ttl_s, summary}` ("go
look" payloads, decision D4): the builder takes no token, key, or VAPID
argument and returns an immutable mapping, so secrets have no ingress
path at construction. Push-construction
only: the owner-facing decision surface keeps showing the full raw text.

## push_sender.py — Web Push send-path transport (#989 / GP1)

The other half of the GP1 sender: `push_crypto.py` proved the crypto but
deliberately has no HTTP layer — this module PINs the transport decisions
and executes one send attempt per call (stdlib-only, side-effect free —
it returns a `PushResult`, never sleeps, never logs).

- **Request:** RFC 8030 POST with `Authorization: vapid t=<jwt>, k=<pubkey>`
  (VAPID `exp` = now + 12 h, `aud` = the endpoint origin per send, `k` =
  the caller's current key — rotation lives with the caller), `TTL:` =
  the payload's own `ttl_s`, `Urgency: high` (page-only channel — D2/D4),
  no `Topic` (never replace a page), `record_size` pinned at 1024
  (deliberate, not the 4096 default; oversized plaintext is rejected
  pre-send, never truncated). No caller salts anywhere — `secrets` mints
  a fresh one per send (finding 7, stated as a rule).
- **TLS:** `https://` endpoints only, no userinfo (cleartext refused —
  a VAPID-signed request never travels unencrypted); hostname + cert
  verification on; connect 5 s / read 10 s. Redirects are never followed
  — any 3xx is a dead-letter (credential-orientation).
- **Result taxonomy** (the per-code table the module docstring pins):
  any 2xx → `accepted` (201 is the RFC 8030 norm, but FCM answers
  successful sends with 200 — record it; feeds #428's §4 email-fallback
  retirement via `acceptance_fields()`); 429 → `retry` honoring
  `Retry-After` (clamped ≤ 600 s) else the 2/8/32/128/300 backoff
  schedule; 410/404 → `tombstone` (caller deletes, dashboard offers
  re-subscribe); 5xx and transport errors → `retry`; 400/401/413, any
  other 4xx, any 3xx → `dead-letter` + operator-visible alert. `retry`
  returns a `retry_after_s` hint — the #990 enqueue machinery owns the
  wait; the module's `MAX_ATTEMPTS = 5` is the policy the caller enforces.
- **Latency:** every attempt reports `latency_ms` (network only — the
  timer starts after crypto + VAPID signing, so VAPID-sign timing is
  excluded from the observable output). Real push-service RTT is still
  unmeasured, and this is the load-bearing input to the
  inline-vs-outbox decision (#990).

Tested by `test_push_sender.py` (30 tests, neutering-verified
non-vacuous) against a stub push service; the stub speaks plain HTTP on
localhost — the difference from production is documented and compensated
by a dedicated test pinning the production transport's TLS policy.
