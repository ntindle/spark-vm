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

(The server computes the fingerprint from the pubkey itself and ignores
the client-sent value — the fingerprint the owner compares is always the
true fingerprint of the submitted key.)
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

## Token rotation (#846)

Box Bearer <redacted> are short-lived (24 h). The box rotates its own token
before expiry — no human involved, no heartbeat dropped:

```bash
spark-pair.py rotate          # rotate now (proof of possession)
spark-pair.py rotate --auto   # cron/systemd: rotate only when the token
                              # expires within 6 h (--within N to change);
                              # quiet success otherwise
```

**How it works.** `rotate` reads `enrollment.json`, signs the message
`b"spark-rotate-v1|<box_id>|<window>"` (`window = floor(now/300)`) with the
box's ed25519 private key, and POSTs it with the current Bearer <redacted>:

```
POST /v1/boxes/token/rotate
Authorization: Bearer <current box token>
{"signature": "<base64 ed25519 signature>"}   # null when the box has no keypair
→ 200 {"ok": true, "token": "<new token>",
       "token_expires_at": <unix>, "proof": "ed25519"|"Bearer <redacted>",
       "rekey_recommended": true?}
```

Proof of possession matters: a stolen Bearer <redacted> alone cannot rotate
the legitimate box out — only the holder of the box private key can mint
the next token. The server accepts the current 300-second window ± 1
(clock skew, in-flight requests) and rotates atomically: the old token
dies on success, and the server keeps the *previous* token valid for a
15-minute grace — accepted on heartbeats AND on the rotate endpoint —
so a box that crashes between the POST and the local save can re-run
`rotate` instead of re-pairing. The client only saves the new token after
validating `token_expires_at` (integer, in the future, at most 48 h out —
a longer "short-lived" token is a misconfigured plane and is refused),
and after checking that a sent signature came back as
`"proof": "ed25519"` (fail-closed: the plane skipping PoP verification
is a refusal, not a save). A bad server response leaves the old
`enrollment.json` untouched — and the write is atomic (temp file +
rename, mode 0600, rechmoded even if the temp file pre-existed).

**401** means the token is dead (expired, revoked, or never valid):
the client says so plainly and exits 1 — re-pair the box (`request` +
`redeem`). **403** means the Bearer <redacted> was accepted but the
proof-of-possession signature was rejected: do NOT re-pair — the
enrollment is healthy; check the box clock (window is ±300 s) and the
plane, then retry; the current token is untouched. **Transport errors**
exit 1 with the cause; `--auto` stays quiet only on the skip path.

**Revocation** (lost/compromised box) is an owner action:

```bash
spark-pair.py revoke --box-id <id>   # SVM_OWNER_KEY or --owner-key
```

```
POST /v1/boxes/{id}/revoke
Authorization: Bearer <owner key>
→ 200 {"ok": true, "revoked": "<id>"}   (404: no such box)
```

The plane stamps `revoked_at` and rejects that box's Bearer <redacted>
immediately — heartbeats, rotation, and bootstrap all 401 from that
moment. Revocation is one-way; the box must be re-paired to come back.
A 404 with a JSON body means no such box; a 404 with no JSON body means
the plane does not implement the endpoint yet (the client says so
instead of claiming the box is missing).

**Server contract checklist (for the plane implementer).**
- `POST /v1/boxes/token/rotate`: Bearer <redacted> auth; `{"signature"}` verified
  against the box's stored pubkey over `spark-rotate-v1|<box_id>|<window>`,
  window ±1; atomic token swap; previous token stays valid 15 min on
  heartbeats and on `/rotate`; new `token_expires_at` = now + 24 h;
  response `{"ok", "token", "token_expires_at", "proof", "rekey_recommended?"}`.
- The plane MUST reject `signature: null` for any box with a pubkey on
  record (null is only for keyless, pre-#844 boxes).
- `POST /v1/boxes/{id}/revoke`: owner auth; stamps `revoked_at`; the
  Bearer <redacted> 401s everywhere immediately.
- Heartbeat stamps NULL `token_expires_at` with now + 24 h on first use
  (grandfathered migration); `token_expires_at` past → 401; revoked → 401.

**Grandfathered tokens.** Boxes enrolled before #844 carry NULL
`token_expires_at` and no keypair. The contract the plane implements:
the first heartbeat after the #846 plane update stamps them with a
24-hour expiry (bounded from then on), and the rotation endpoint accepts
a null `signature` for keyless boxes (`"proof": "Bearer <redacted>"`,
`"rekey_recommended": true`) — weaker than proof-of-possession, but
bounded. The client sends `signature: null` when no `box.key` exists.
Re-pairing (`request` + `redeem`) gives the box a keypair and full
proof-of-possession rotation.

**Status.** The control-plane half is live on the hosted control
plane (deployed 2026-10-02): `POST /v1/boxes/token/rotate` and
`POST /v1/boxes/{id}/revoke` serve, the `revoked_at` / `prev_token_hash` /
`prev_token_valid_until` columns are migrated, and heartbeats stamp the
24 h expiry on grandfathered tokens. This client implements the full
contract above — verify with a manual `rotate` before installing the
cron line below. Do not install the cron line below until your
control plane serves the endpoints — verify with a manual `rotate` first.

**Automation.** Once the plane serves the endpoints, a box operator keeps
the token fresh with a cron line or systemd timer, e.g. hourly:

```
0 * * * * /path/to/spark-pair.py rotate --auto >>/var/log/spark-rotate.log 2>&1
```

## Heartbeat (#864)

The control plane's liveness contract is a single box-side call — the
fleet dashboard's staleness chips are honest only if something actually
sends it:

```bash
spark-pair.py heartbeat   # one POST /v1/boxes/{id}/heartbeat, then exit
```

One invocation sends exactly one heartbeat with the box's current Bearer <redacted>
(from `enrollment.json`, so `rotate --auto` keeps this working with no
changes) and a small JSON status body (`box_id`, `sent_at`, the client
identity, box uptime, 1-minute load, and the token's own expiry as a
self-report — the plane enforces expiry from its own store). The contract
with the operator:

- **Exit 0 only on the plane's own `{ok:true}`.** A missed heartbeat never
  fabricates an ok — every other outcome (transport error, HTTP error, a
  200 that doesn't say ok) exits 1.
- **Failures are loud.** Every failure prints to stderr AND is appended to
  `heartbeat.log` in the state dir. Success is quiet: a healthy box emits
  nothing, so the every-minute cron line stays silent.
- **The token never reaches a log.** Failure messages redact the Bearer <redacted>
  before they touch stderr or `heartbeat.log`.
- **Last success is checkable locally:** `last_heartbeat.json` records the
  last tick the plane confirmed, so an operator can see freshness without
  asking the dashboard.

Cron-acceptable (like `rotate --auto`), with a lock file so a slow plane
can't stack overlapping invocations:

```
* * * * * /path/to/spark-pair.py heartbeat >>/var/log/spark-heartbeat.log 2>&1
```

This is the *interim* sender: no box long-lived process, no reconnect
loop. The persistent box-side process for the phone-home WebSocket is
decided with the #847 S5 box WSS client, not here.

## Command ingest (#874)

The other half of the approvals return leg: the plane enqueues owner
decisions as `approval_decision` commands on the durable queue (#848,
#873), and the box has to consume them — otherwise a parked agent never
learns the owner tapped approve/deny on the plane dashboard:

```bash
spark-pair.py ingest   # one fetch-execute-ack pass, then exit
```

One invocation fetches due commands (`GET /v1/boxes/{id}/commands/pending`
with the box Bearer), executes the ones it honors, acks them, and advances
its cursor — the cursor is the highest *acked* seq (never highest-fetched),
persisted in `commands_cursor.json`, healed from the plane's
`acked_watermark` when the file is missing or corrupt. The contract with
the operator mirrors `heartbeat`:

- **Exit 0 only when every due command was consumed.** A command the ingest
  could not execute is *not* acked — it redelivers on the next tick — and
  the run stops at it, so the cursor can never advance past an unacked
  command and skip its redelivery.
- **Failures are loud.** Every failure prints to stderr AND is appended to
  `ingest.log` in the state dir; the token is redacted from both channels.
  A 401 names re-pairing; a plane without the commands endpoints says so
  honestly instead of failing opaquely.
- **Lock file** (`.ingest.lock`) serializes overlapping cron ticks.

`approval_decision` is the only honored command kind today; unknown kinds
are acked-and-logged so one unknown kind cannot wedge the queue (note
the version-skew hazard: a plane-produced kind this client does not
understand is skipped *semantically*, not just executionally — a new
honored kind needs an ingest update; see `docs/DURABLE_COMMANDS.md`).
Each decision is validated (aid shape, decision word, `decision_seq`,
and the idempotency key bound to `box_id`+`aid`+`seq`), then stamped
into confirmd's answered/consumed store exactly like a local tap —
`deny` and `expire` land the terminal records the proxy's Decision legs
read, and `approve` mints the grant through confirmd's single writer
(`proxy/grant-writer`, which dedupes on approval id, so a crash between
mint and stamp cannot double-mint on redelivery). Every stamped record
carries `decision_origin: "plane"` plus the plane's `(seq,
idempotency_key)` as the receipt, and a decision is stamped only for an
aid the box itself filed — a decision for an unknown aid is rejected,
never stamped. Stated plainly: this makes the plane a **grant-issuing
authority** — a compromised plane can mint arbitrary local grants
through the approve path; that is the feature's purpose (the owner's
tap moved to the plane dashboard), and the box already trusts the plane
for pairing, token rotation, and liveness. A tenant-scoped item is
permanently unprocessable for this pre-H10 client: it is acked-and-logged
loudly with the upgrade runbook (the run exits 1 for operator
attention) rather than wedging the queue; a scoped item whose window
already lapsed is stamped expired honestly, which drains it.

Mode note: the approve path mints through `proxy/grant-writer` against
the box's **local secrets dir** — the self-hosted mode, and the only
mode this implementation supports. Vend-mode boxes (#891) must not run
the local-mint approve path; the dual-mode seam is #891's scope (see
`docs/DURABLE_COMMANDS.md`). Every stamped decision — `deny`,
`expire`, `approve` — also appends one `answer` line to confirmd's
audit log (same shape as the local answer path, plus
`decision_origin=plane`), so plane decisions never bypass the audit
trail.

Cron-acceptable:

```
* * * * * /path/to/spark-pair.py ingest >>/var/log/spark-ingest.log 2>&1
```

The approvals store is located via `SVM_APPROVALS_DIR` (default
`/home/swapd/approvals`, the proxy's default); the grant writer via
`GRANT_WRITER` (default `/home/swapd/grant-writer`, confirmd's default).

## Filing upload (#953)

The other half of the approvals return leg: the proxy files refused-grant
approvals locally only (`confirm/pending/<aid>.json`), and the plane
record (#872) plus the box-authenticated file endpoint (#952) give it a
destination — but nothing moves the filing across. The uploader closes
that leg:

```bash
spark-pair.py upload-filings   # one scan-and-POST pass, then exit
```

One invocation scans `confirm/pending/` (never the summons outbox
journal — the journal is append-only and serves the summons observer)
and POSTs each still-pending filing to the plane's
`POST /v1/boxes/{id}/approvals/file` with the box Bearer. The contract
with the operator mirrors `heartbeat`/`ingest`:

- **Periodic, not inline.** The proxy refusal hot path never gains plane
  latency or a plane-failure coupling: a plane outage degrades loudly
  but the local filing keeps working — the pending record stays and the
  next tick retries.
- **Exit 0 only when every pending filing was uploaded, already on the
  plane, or locally expired (skipped).** The plane dedupes on `(box_id,
  aid)`, so a retried filing returns `deduped: true` instead of a
  duplicate — the retry loop is idempotent by construction.
- **Failures are loud.** Every failure prints to stderr AND is appended to
  `upload-filings.log` in the state dir; the token is redacted from both
  channels. A 401 names re-pairing (and aborts the pass — a dead token
  poisons every filing); a plane without the file endpoint says so
  honestly instead of failing opaquely.
- **Lock file** (`.upload-filings.lock`) serializes overlapping cron ticks.
- **Pending-only.** Denied, expired-stamped, and consumed records live
  outside `pending/` and are never seen; a locally-expired record is
  skipped too (it is on its way to `consumed/`, and uploading it would
  mint a plane-side ghost). The ingest's first-terminal-wins check stays
  the real divergence gate.
- **Writer identity.** The pending dir must be box-service-owned
  (`bdrive`/`swapd` — the same DAC-owner discipline ingest enforces per
  record): an agent-owned store is refused, never uploaded.
- **Payload mapping** (per `docs/FILING_UPLOAD_GAP_ANALYSIS.md` G76.3):
  `aid` is the plane's idempotency key; the local (unbounded) summary is
  clipped to 250 + "…"; the detail tuple
  `{credential, host, method, path_prefix, reason, filed_at, expires}`
  carries no free text (Finding-49 discipline), and `path_prefix` is
  truncated with "…" (full host kept) so a pathological filing can never
  breach the plane's 4 KB detail cap.

Cron-acceptable:

```
* * * * * /path/to/spark-pair.py upload-filings >>/var/log/spark-upload-filings.log 2>&1
```

## Phone-home channel (#959 S5a connection core + #976 S5b socket commands)

> **Plane half not built yet.** The one-Durable-Object-per-box plane half
> (#958) that serves the upgrade endpoint does not exist — against a
> current plane this daemon retries `upgrade failed` with backoff until
> it lands. This slice was validated against a stub harness only (see
> `pairing/test_phone_home.py`); live-plane acceptance is #960.

The persistent outbound WSS channel from the box to the control plane,
per `docs/PHONE_HOME_WIRE_PROTOCOL.md` (the S3 contract). Unlike the
cron-shaped commands above, this one is a daemon — it holds the socket
open and reconnects per the wire spec's close taxonomy:

```bash
spark-pair.py phone-home   # daemon: runs until SIGTERM/SIGINT or a fatal close
```

Run it under a supervisor, not cron:

```ini
[Unit]
Description=spark-vm phone-home channel
After=network-online.target

[Service]
ExecStart=/path/to/spark-pair.py phone-home
Restart=on-failure
RestartPreventExitStatus=1
RestartSec=5
# Exit 1 means HUMAN ATTENTION, not a restart loop: fatal closes (revoked
# token, protocol errors) exit 1 deliberately, and RestartPreventExitStatus
# keeps those deliberate exits dead — a supervisor restarting blindly would
# recreate the reconnect storm the daemon refuses, notably on `revoked`,
# where re-pairing the box is the human path. Crashes and signals still
# restart under on-failure. Alert on repeated restarts instead of
# restarting forever.

[Install]
WantedBy=multi-user.target
```

`phone_home.log` in the state dir is append-only (one line per
connection-lifecycle event, never per keepalive ping); rotate it with
logrotate `copytruncate` or ship it to your log aggregator.

**Exit codes:** `0` — stopped on SIGTERM/SIGINT. `1` — fatal, needs a
human: revoked token (re-pair with `request` + `redeem`), a second
session under this identity (`superseded-generation`), a client or plane
bug (`identity-mismatch` / `protocol-error` / unknown close code), or
enrollment/rotate failures.

What it does:

- **Upgrade.** Derives `wss://` from the control URL (loopback `ws://`
  stays allowed, same as the cleartext discipline everywhere else),
  speaks the HTTP/1.1 upgrade by hand — there is no redirect-following
  on this path by construction (any 3xx is an upgrade failure), and the
  `Sec-WebSocket-Accept` is validated. The box Bearer <redacted> in the
  `Authorization` header only: never in a frame, never in `phone_home.log`.
- **Generation fence.** A crash-safe durable counter
  (`phone_home_generation.json`, persisted before use so a crash skips a
  value, never reuses one); `hello` carries it, and a `stale-generation`
  close makes the client adopt the DO's `last_generation + 1` and bump
  the ingest epoch (counter loss is a reboot-equivalent per the spec).
  Plain reconnects bump the generation only — never the epoch.
- **Reconnect policy.** `revoked` → no reconnect loop (re-pair is the
  human path); `expired` → reconnect with the current token (one rotate
  attempt only when no live token is held); `going-away` → wait ≥ 60 s;
  silent transport loss → 1 s doubling backoff, 60 s cap, ±25% jitter.
  `identity-mismatch` / `protocol-error` / unknown close codes exit loud
  without reconnecting — a protocol bug must never become a reconnect
  storm. An upgrade `401` gets exactly one rotate attempt, then re-pair
  guidance.
- **Keepalive.** JSON `ping` every 30 s; no `pong` within 90 s drops the
  socket. The #864 heartbeat stays the ONLY liveness signal — this
  client never writes `last_heartbeat.json`.
- **One writer.** A `.phone-home.lock` is held for the daemon's life; a
  second instance exits instead of forking the generation counter.

Command frames ride the socket too (S5b, #976): `command` frames
dispatch into the same #874 ingest executor the HTTPS fetch path uses
(execute-before-ack, dedupe by `(box_id, seq)` through the shared
idempotency log + `consumed/` records), and `command_ack` frames go back
over the socket — the wire spec's §3.3 socket-vs-HTTPS choice, decided
for the socket (same session, generation-bound, DO-direct; the HTTPS
`/commands/ack` endpoint stays as the fetch path's ack). The acked
prefix never skips a bad row: a malformed, oversized (> 16 KiB), or
wrong-generation frame is logged loudly and never acked, and a seq gap
holds the prefix until the DO's re-drive heals it — the same
never-advance-past-unacked invariant as the HTTPS cursor.

## Security properties

- **No self-registration.** The old register endpoint is gone (404). A box
  becomes enrolled only after a human approves its pairing — normally an
  owner-key holder; on a fresh database only, the first-claim bootstrap
  (see below) until the first owner key exists.
- **Proof of possession.** Redeem requires an ed25519 signature over a
  server-issued 32-byte challenge, verified against the pubkey submitted at
  request time. Requesting a pairing for someone else's box name gains
  nothing: the server fingerprints the submitted pubkey itself, so the
  attacker's key shows a different fingerprint than the real box displays —
  and the owner compares the fingerprint out-of-band before approving.
- **Human binding.** Approval requires the owner to type the pairing code
  shown on the box's screen, and to verify the key fingerprint out-of-band
  (read it off the box). An attacker who can request pairings cannot
  approve them.
- **Bounded windows.** Pairing codes expire after 15 minutes (lazy expiry on
  read); the issued bearer token expires after 24 hours.
  `spark-pair.py rotate --auto` (cron/systemd) replaces the token before
  expiry with proof-of-possession rotation (#846); a dead token (401/403)
  means re-pair the box. At most 50 pairings may be pending at once
  (429 beyond that).
- **Secret hygiene.** Pairing codes are stored as SHA-256 hashes; bearer
  tokens and owner keys as SHA-256 hashes; the box private key never leaves
  the box; the token is shown exactly once at redeem. List/detail endpoints
  never return code hashes or challenges.
- **Pre-#844 tokens** carry NULL `token_expires_at` — grandfathered until #846 migrates them to rotation.

## Files

- `ed25519.py` — pure-Python Ed25519 (RFC 8032), stdlib only. Used by the
  box client (keygen/sign) and inlined into the control-plane Worker
  (signature verification; the Worker deploys as a single file).
  `test_ed25519.py` asserts the two copies stay byte-identical.
- `spark_pair.py` — box client + owner approval CLI (stdlib only):
  `init`, `request --name`, `redeem`, `approve [--pairing-id]`,
  `heartbeat`, `rotate [--auto]`, `revoke --box-id`,
  `ingest` (durable-command consumer, #874).
  State in `~/.config/spark-pair` (`--dir` / `SVM_PAIR_DIR` override);
  key and token files are mode 0600; secrets are never printed.
  Control-plane URL defaults to `https://api.sparkvm.dev`
  (`--control` / `SVM_CONTROL` override). The client refuses cleartext
  `http://` control planes (credentials would travel unencrypted) — loopback
  hosts stay allowed for local testing, and `SVM_PAIR_ALLOW_HTTP=1` opts in
  explicitly for other hosts. Redirects that leave the original origin have
  the `Authorization` header stripped, so a redirect chain can never carry
  the box bearer token or owner key to another host. Owner key via `SVM_OWNER_KEY`
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
| POST | /v1/boxes/{id}/heartbeat | box Bearer <redacted> | `{box_id, sent_at, client, uptime_s?, load_1?, token_expires_at?}` → `{ok:true}` — box liveness (~60 s cadence; dashboard marks stale after 300 s). Sent by `spark-pair.py heartbeat` (#864). |
| POST | /v1/boxes/token/rotate | box Bearer <redacted> | `{"signature": b64|null}` → `{token, token_expires_at, proof}` — proof-of-possession rotation (#846; live on the hosted plane since 2026-10-02) |
| POST | /v1/boxes/{id}/revoke | owner | revoke the box's Bearer <redacted> immediately (#846; live on the hosted plane since 2026-10-02) |
| GET | /v1/boxes/{id}/commands/pending | box Bearer <redacted> | `?since=&limit=` → `{commands, acked_watermark, lease_secs}` — due durable commands, current epoch, `seq > since` (#848; consumed by `spark-pair.py ingest`, #874) |
| POST | /v1/boxes/{id}/commands/ack | box Bearer <redacted> | `{seqs:[...]}` — idempotent ack of executed commands (#848; consumed by `spark-pair.py ingest`, #874) |
| POST | /v1/boxes/{id}/approvals/file | box Bearer <redacted> | `{aid, summary, detail?, expires_in_secs}` → `201/200 {ok, aid, deduped}` (write-only — never the record body) — box files its own pending approvals; idempotent on `(box_id, aid)`; `current`+`grace` token states accepted (#952; consumed by `spark-pair.py upload-filings`, #953; live on the hosted plane since 2026-10-03) |

## Trying it

```bash
python3 pairing/spark_pair.py init
python3 pairing/spark_pair.py request --name garage-box
# read the code + fingerprint off the box, then on any machine:
SVM_OWNER_KEY=... python3 pairing/spark_pair.py approve --pairing-id pair_...
python3 pairing/spark_pair.py redeem

# keep the token fresh (cron/systemd runs `rotate --auto` hourly):
# NOTE: rotate/revoke need the control-plane endpoints that closed #846
# (live on the hosted plane since 2026-10-02; self-hosted planes need the
# update) — verify with a manual `rotate` before installing the cron line
# (see Token rotation in this README).
python3 pairing/spark_pair.py rotate --auto
# owner revokes a lost/compromised box immediately:
SVM_OWNER_KEY=... python3 pairing/spark_pair.py revoke --box-id box_...
# box liveness (~every minute, quiet on success, loud on failure):
# * * * * * /path/to/spark-pair.py heartbeat >>/var/log/spark-heartbeat.log 2>&1
# plane approval decisions -> confirmd's store (~every minute):
# * * * * * /path/to/spark-pair.py ingest >>/var/log/spark-ingest.log 2>&1
python3 pairing/spark_pair.py heartbeat
```

## First-owner-key bootstrap

On a fresh database there are no owner keys yet, so the approve call cannot
carry one. While `owner_keys` is empty, `POST /v1/pairing/{id}/approve`
accepts the correct typed pairing code with no `Authorization` header and
records the approval as `approved_by='bootstrap'`; `GET /v1/pairing/{id}`
is likewise readable so the human can verify the fingerprint first. The
client spells this `approve --pairing-id pair_... --bootstrap`.

Honest threat model: `/v1/pairing/request` is public, so on a fresh
database anyone who can reach the Worker can request a pairing and
self-approve it — the first party to complete
request → approve → redeem → owner-bootstrap becomes the owner
(first-claim race). The pairing id is 64-bit (`pair_` + 16 hex chars) and
the code 40-bit (hashed): not guessable, but not a secret either. The
operator wins the race by enrolling immediately after deploy on a trusted
network; the window closes permanently at the first owner key. There is no
better answer without a setup secret (deliberately removed in #843); the
alternative is an unenrollable fresh database.
