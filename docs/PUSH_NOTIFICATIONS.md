# Push notifications for confirmd approvals (H2 / GitHub #2)

confirmd can push a Web Push notification to the owner's devices the
moment swapd files an approval — so the two-tap approval loop works even
when the approvals page isn't open.

This is a **portable component**, not a hosted-only service: the operator
runs it wherever the deployment lives (self-hosted box or hosted
service). The VAPID keypair is operator-generated during setup; no real
secrets ever live in the repo.

## How it works

1. **Setup (operator, once):**
   ```sh
   sudo -u swapd python3 /home/swapd/push.py --gen-keys /home/swapd/confirmd/vapid.json
   # writes {"private","public"} base64url, mode 0600, refuses to overwrite
   sudo systemctl restart confirmd
   ```
   confirmd logs `PUSH_ENABLED=True` at startup. The protocol is
   RFC 8030 (Web Push) + RFC 8292 (VAPID) + RFC 8291 (aes128gcm payload
   encryption), implemented in `confirm/push.py` on top of the
   `cryptography` package. Without the key file (or without
   `cryptography` installed), push is disabled and the page works
   exactly as before.

2. **Subscribe (human, once per browser):** open the confirmd pending
   page → "Enable notifications". The browser's PushManager subscribes
   with the server's VAPID public key (served at `/api/push/config` —
   public by design), and the subscription (endpoint + `p256dh` + `auth`)
   is POSTed to `/api/push/subscribe`. The button only appears when the
   browser supports push and the server reports it enabled.

3. **Notify (automatic):** when swapd files an approval
   (`swap_addon._file_approval`), it calls
   `PushSender.default().notify_approval(item)` — one encrypted push per
   stored subscription. The service worker (`/sw.js`) shows the
   notification; tapping it opens `/approval/<id>`.

## Security notes

- **Key storage:** the VAPID private key lives at
  `/home/swapd/confirmd/vapid.json`, mode 0600, owned by swapd. It is
  generated on the box, never committed, never logged. `--gen-keys`
  refuses to overwrite an existing file.
- **Payload contents:** the encrypted payload carries only the approval
  summary (the same text the page already shows) plus the approval id —
  never secrets, never model-authored free text (finding 49). The
  notification URL is built relative to the page's own origin, so there
  is no origin confusion between the tailnet IP and the ts.net name.
- **Subscribe endpoint:** `/api/push/subscribe` and `/api/push/unsubscribe`
  are owner-authenticated exactly like the page (`_auth`), with the same
  CSRF defenses as `/answer` (Sec-Fetch-Site + exact Origin match, 4 KB
  body cap). Subscription material is validated strictly: https-only
  endpoints, 65-byte uncompressed `p256dh`, 16-byte `auth`.
- **Audit trail:** subscribes/unsubscribes are audit-logged (endpoint
  host only — the full URL carries an opaque push-service token).
  Dead subscriptions (push service returns 404/410) are pruned
  automatically.
- **Fail-open by design:** a push failure (no keys, network down, bad
  subscription) never loses the filed approval — the approval file is
  written first, and every push path catches and logs instead of
  raising. `notify_approval` is idempotent per approval id (a
  `push-notified` log, capped at 1000 entries) so retries can't
  double-notify.
- **Per-device, not per-tenant:** subscriptions are stored per box in
  `$CONFIRM_DIR/push-subscriptions.json` (mode 0600, atomic writes).
  Per-tenant queues (H10) will need per-tenant subscription scoping —
  that is follow-up work, not this slice.

## Configuration reference

| Env | Default | Purpose |
|---|---|---|
| `CONFIRM_VAPID_KEYS` | `/home/swapd/confirmd/vapid.json` | VAPID keypair JSON |
| `CONFIRM_PUSH_SUBS` | `$CONFIRM_DIR/push-subscriptions.json` | subscription store |
| `CONFIRM_VAPID_SUB` | `mailto:confirmd@localhost` | VAPID `sub` contact claim |

## Follow-ups (not this slice)

- H14 (push service): a standalone push service with enqueue/hook
  semantics instead of the in-`_file_approval` call.
- Per-tenant subscription scoping (needs H10/H11).
- iOS Safari note: Web Push on iOS requires the page added to the home
  screen; the subscribe button reports "push not supported" otherwise.
