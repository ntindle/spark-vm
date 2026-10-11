# Hosted control-plane auth: operator runbook

This is the operator's page for the hosted control plane's auth stack
(#843 owner API keys, #844 pairing-code enrollment, #846 short-lived box
tokens + rotation, #864 box heartbeat). It says what each credential is,
who holds it, and what to do when something breaks. The contract details
live where they are implemented (repo-root-relative paths where they
exist): `pairing/README.md` (the box-client contract), the control-plane
checkout's `worker.py` (the endpoint table in its module docstring — the
source of truth), and its `schema.sql` (what the plane stores).

## The credential inventory

There are exactly two credential classes, in separate namespaces. A box
Bearer <redacted> presented at an owner endpoint never matches, and an owner
key presented at a box endpoint never matches — a stolen credential from one
class buys nothing in the other.

| Credential | Format | Plane stores | Operator/box holds | TTL |
|---|---|---|---|---|
| Owner API key | `svm_` + 43 urlsafe chars | SHA-256 hash only (`owner_keys.key_hash`) | Operator: the plaintext once, at creation; the dashboard keeps it only in the tab's `sessionStorage` (never cookie, `localStorage`, or URL) | **None** — long-lived; mint a replacement with `POST /v1/owner/keys` before revoking |
| Box bearer token | opaque | SHA-256 hash only (`boxes.token_hash`) | Box: `enrollment.json`, mode 0600 | 24 h (`token_expires_at`); the previous token stays valid 15 min on heartbeats and `/rotate` after a rotation (crash recovery) |
| Box ed25519 keypair | RFC 8032 | Public key only (`boxes.pubkey`) | Box: private key in the state dir, mode 0600 — **never leaves the box** | Lives with the enrollment |
| Pairing code | 8 chars, shown once | SHA-256 hash only (`pairings.code_hash`) | Operator: reads it off the box screen | 15 min (lazy expiry on read); at most 50 pairings pending at once (429 beyond) |

No Bearer <redacted> secret — owner key or box token — ever reaches a log:
the pairing client redacts the Bearer <redacted> before anything touches
stderr or log files.

## Day 0: bootstrap

On a fresh database there are no owner keys. Two one-shot legs exist, and
both close permanently at the first owner key:

1. **Pairing first-claim** (the usual path): run `request` on the box, read
   the code + fingerprint off the box screen, and approve with the code and
   no `Authorization` header (`approve --pairing-id pair_... --bootstrap`).
   Threat model, stated honestly: `/v1/pairing/request` is public, so on a
   fresh database anyone who can reach the Worker can request and
   self-approve — the first party to complete
   request → approve → redeem → bootstrap becomes the owner. Win the race
   by enrolling immediately after deploy on a trusted network.
2. **`POST /v1/owner/bootstrap`** with `Authorization: Bearer <box-token>`
   (a token from an already-enrolled box) → `{ok: true, id, key}` once.
   After any active owner key exists it returns 403
   (`"error": "bootstrap closed"`); the empty-table check runs *before*
   token validation, so a closed bootstrap leaks nothing about token
   validity. There is no setup secret — a box-token holder bootstrapping
   *is* the owner.

**Save the minted key immediately.** It is returned exactly once and the
plane stores only its hash. There is no "show me my key" endpoint.

Operator gotcha: on a fresh database the very first pairing approval is
CLI-only (`spark_pair.py approve --bootstrap`) — the dashboard can't sign
in until that first owner key exists, so don't reach for the dashboard
first.

## Owner keys, day-to-day

- `GET /v1/owner/keys` → key metadata (ids, names, created times) — never
  hashes, never plaintexts.
- `DELETE /v1/owner/keys/{id}` revokes a key. The last-active-key guard
  lives *inside* the UPDATE, so two concurrent revokes can't both pass it:
  the plane always keeps at least one active owner key. 404 means the id
  is unknown or already revoked.
- **Minting additional keys (#878, shipped):** `POST /v1/owner/keys` with
  an owner key mints a new one — JSON `{"name": "..."}` is optional
  (1–64 chars; absent defaults to the key id). 201 returns
  `{id, key, warning}` with the plaintext exactly once; it is never
  stored and `GET /v1/owner/keys` still shows metadata only. A box token
  presented here 401s — owner keys and box tokens are separate namespaces.
- **Safe owner-key rotation (the #878 story):** mint a second key with
  the current one → verify the new key authenticates (`GET /v1/owner/keys`
  with it) → revoke the old key. The last-active-key guard keeps at least
  one active key, so this is two-step by construction and you can never
  lock yourself out. A second operator gets a second key the same way
  (name it for them); a lost key now costs a mint, not a fresh database.
- Owner keys have **no expiry** (`owner_keys` carries no `expires_at`;
  validity is `revoked_at IS NULL`). The box-side tokens they authorize are
  the short-lived ones.

## Enrolling and keeping a box alive

The full flow is `pairing/README.md` — this is the operator's checklist:

1. `spark-pair.py init` on the box (keypair stays on the box).
2. `spark-pair.py request --name <box>` → read the code + fingerprint off
   the box screen; on your machine approve with the owner key, comparing
   the fingerprint out-of-band. The server computes the fingerprint from
   the submitted pubkey itself, so an attacker can't substitute one.
3. `spark-pair.py redeem` (ed25519 proof-of-possession over the
   server-issued challenge) → token saved 0600.
   - **Golden image:** redeem against the hook's state dir, then propagate
     the plane-push signal so the swapd push worker stands down quietly:
     `python3 pairing/spark_pair.py --dir /root/.config/spark-pair redeem`
     followed by `sudo identity-seed-hook.sh --propagate-plane-push-signal`
     (see `deploy/golden-image/README.md`).
4. Install both cron lines **after verifying the plane serves the
   endpoints** (a manual `rotate` and a manual `heartbeat` first):
   - `0 * * * * /path/to/spark-pair.py rotate --auto` — rotates only when
     the token expires within 6 h (`--within N` to change); quiet success.
   - `* * * * * /path/to/spark-pair.py heartbeat` — one-shot liveness POST
     every minute; exit 0 only on the plane's own `{ok:true}`; every
     failure is loud (stderr + `heartbeat.log`); last plane-confirmed tick
     in `last_heartbeat.json`.

The heartbeat sender is the interim one (issue #864): no persistent
box-side process, no reconnect loop. The persistent phone-home design is
the #847 box WSS client — not here.

## Incident response

**Box lost or compromised → revoke, then re-pair.**
`POST /v1/boxes/{id}/revoke` (owner key) stamps `revoked_at` and that box's
Bearer <redacted> 401s *immediately* — heartbeats, rotation, and bootstrap
all refuse it from that moment. Revocation is one-way: the box comes back
only by re-pairing (`request` + `redeem`).

**Owner key leaked → mint a replacement, then revoke the leaked one.**
Mint a new key (`POST /v1/owner/keys`) with the key you still hold,
verify it authenticates, then revoke the leaked key
(`DELETE /v1/owner/keys/{id}`); the last-active-key guard prevents
locking yourself out. Keep a saved backup key regardless — two live
keys is the minimum sane posture.

**A 401 on the box → re-pair, don't fight it.** 401 means the token is dead
(expired, revoked, or never valid): `request` + `redeem` again.

**A 403 on `rotate` → check the clock, don't re-pair.** 403 means the
Bearer <redacted> was accepted but the proof-of-possession signature was
rejected — the enrollment is healthy. The signature window is ±300 s; fix
the box clock and retry. The current token is untouched.

**A 404 without a JSON body → the plane doesn't implement the endpoint.**
A 404 *with* a JSON body means "no such box". Never mistake the former
for the latter — the client distinguishes them for exactly this reason.

**429 on pairing requests → back off.** More than 50 pairings are pending;
an operator approves the real ones or waits for the 15-minute expiry.

## Failure-code table

| Code | Meaning on this plane | Operator action |
|---|---|---|
| 401 | Token dead (expired, revoked, never valid) | Re-pair the box (`request` + `redeem`) |
| 403 | Bearer <redacted> ok, proof-of-possession rejected (`rotate`) | Fix box clock (±300 s window), retry; do NOT re-pair |
| 403 `"bootstrap closed"` | An owner key already exists | Use your owner key; bootstrap is one-shot |
| 404 with JSON body | No such box / key id | Check the id; don't invent one |
| 404 without JSON body | Plane doesn't implement the endpoint | Update the plane (self-hosted) before concluding the box is missing |
| 429 | Pairing cap (50 pending) | Approve the real pairings or wait out the 15-min expiry |

## What NOT to do

- Never commit, paste, or log a plaintext key or token — they are shown
  once at creation and live only in 0600 files, `sessionStorage`, or your
  own secret store.
- Never treat a missed heartbeat as an ok — exit codes and
  `last_heartbeat.json` are the freshness signal, never "no news".
- Never bypass the ±300 s clock-skew guidance by re-pairing a 403'd box —
  re-pairing destroys a healthy enrollment.
