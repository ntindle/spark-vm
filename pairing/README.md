# Pairing-code box enrollment

Issue [#844](https://github.com/ntindle/spark-vm/issues/844): bounded,
human-approved enrollment replaces the old `POST /v1/boxes/register`. No box
can self-register without a human approving it, pairing codes expire, and
the whole flow is outbound-only — it works for self-hosted boxes
(Unraid/Proxmox/etc.) with no inbound ports.

## The flow

```
box (spark_pair.py)                          control plane               owner
─────────────────                            ──────────────              ─────
init: generate ed25519 keypair locally
  (private key never leaves the box)

request --name mybox ──POST /v1/pairing/request──▶  stores: code_hash,
  {name, pubkey, fingerprint}                      pubkey, fingerprint
◀── {pairing_id, code, expires_at} ──              code: 8 chars, 15-min TTL
box prints CODE + FINGERPRINT ──────────────────────────────────▶ owner reads
                                                                   them off
                                                                   the box
                                              GET /v1/pairing ──▶ owner lists
                                              (owner key)          pending
                                              GET /v1/pairing/{id}
                                              (owner key)          owner compares
                                                                   fingerprint
                                                                   with the box
                                                                   screen, types
                                                                   the code
                                              POST /v1/pairing/{id}/approve
                                              {code} (owner key) ─▶ approved;
                                                                   challenge
                                                                   nonce issued
box polls GET /v1/pairing/{id}/status ◀── {approved, challenge} ──
redeem: sign(challenge) ──POST /v1/pairing/{id}/redeem──▶ verifies ed25519
  {signature}                                     signature vs stored pubkey
◀── {box_id, token, token_expires_at} ──          pairing consumed (one-shot)
box saves token (0600), heartbeats as before
```

## Security properties

- **No self-registration.** The old register endpoint is gone (404). A box
  becomes enrolled only after an owner-key holder approves its pairing.
- **Proof of possession.** Redeem requires an ed25519 signature over a
  server-issued 32-byte challenge, verified against the pubkey submitted at
  request time. Requesting a pairing for someone else's box name gains
  nothing: the fingerprint won't match what the real box displays.
- **Human binding.** Approval requires the owner to type the pairing code
  shown on the box's screen, and to verify the key fingerprint out-of-band
  (read it off the box). An attacker who can request pairings cannot
  approve them.
- **Bounded windows.** Pairing codes expire after 15 minutes (lazy expiry on
  read); the issued bearer token expires after 24 hours (rotation is #846).
  At most 50 pairings may be pending at once (429 beyond that).
- **Secret hygiene.** Pairing codes are stored as SHA-256 hashes; bearer
  tokens and owner keys as SHA-256 hashes; the box private key never leaves
  the box; the token is shown exactly once at redeem. List/detail endpoints
  never return code hashes or challenges.
- **Pre-#844 tokens** (`box_7dccb3da`, the live box) carry NULL
  `token_expires_at` — grandfathered until #846 migrates them to rotation.

## Files

- `ed25519.py` — pure-Python Ed25519 (RFC 8032), stdlib only. Used by the
  box client (keygen/sign) and inlined into the control-plane Worker
  (signature verification; the Worker deploys as a single file).
  `test_ed25519.py` asserts the two copies stay byte-identical.
- `spark_pair.py` — box client + owner approval CLI (stdlib only):
  `init`, `request --name`, `redeem`, `approve [--pairing-id]`.
  State in `~/.config/spark-pair` (`--dir` / `SVM_PAIR_DIR` override);
  key and token files are mode 0600; secrets are never printed.
  Control-plane URL defaults to `https://api.sparkvm.dev`
  (`--control` / `SVM_CONTROL` override). Owner key via `SVM_OWNER_KEY`
  or an interactive prompt (never argv).

## Control-plane endpoints (see control-plane/worker.py)

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | /v1/pairing/request | none | `{name, pubkey(b64), fingerprint}` → `{pairing_id, code, expires_at}` |
| GET | /v1/pairing | owner | pending/approved pairings (no code material) |
| GET | /v1/pairing/{id} | owner | detail incl. fingerprint |
| POST | /v1/pairing/{id}/approve | owner | `{code}` typed by the human |
| GET | /v1/pairing/{id}/status | none | box polls; `{challenge}` only when approved |
| POST | /v1/pairing/{id}/redeem | none | `{signature(b64)}` → `{box_id, token, token_expires_at}` |

## Trying it

```bash
python3 pairing/spark_pair.py init
python3 pairing/spark_pair.py request --name garage-box
# read the code + fingerprint off the box, then on any machine:
SVM_OWNER_KEY=... python3 pairing/spark_pair.py approve --pairing-id pair_...
python3 pairing/spark_pair.py redeem
```
