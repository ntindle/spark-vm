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
   # Prerequisite (Ubuntu 24.04): the cryptography package. Use apt —
   # bare `pip install cryptography` fails under PEP 668's
   # externally-managed-environment policy.
   sudo apt install -y python3-cryptography

   sudo -u swapd python3 /home/swapd/push.py --gen-keys /home/swapd/confirmd/vapid.json
   # writes {"private","public"} base64url, mode 0600, refuses to overwrite
   sudo systemctl restart confirmd
   ```
   confirmd logs `PUSH_ENABLED=True` at startup. If push is disabled it
   logs the concrete reason instead, e.g. `PUSH_DISABLED_REASON=no-keys:
   /home/swapd/confirmd/vapid.json unreadable or invalid (...)` or
   `no-cryptography: ...` — the same value is served at
   `/api/push/config` as `disabled_reason`, so the status line can tell
   the operator exactly what is missing. The protocol is RFC 8030
   (Web Push) + RFC 8292 (VAPID) + RFC 8291 (aes128gcm payload
   encryption), implemented in `confirm/push.py` on top of the
   `cryptography` package. Without the key file (or without
   `cryptography` installed), push is disabled and the page works
   exactly as before.

2. **Verify (operator):** open the confirmd page (e.g.
   `http://127.0.0.1:18735/` through the SSH tunnel) — with keys
   configured and a supported browser you see an **Enable notifications**
   button under the pending list; without keys the status line names the
   missing piece. Then subscribe a test device and run:
   ```sh
   sudo -u swapd python3 /home/swapd/push.py --test-push
   # test push test-<ts>: 1 subscription(s) accepted it
   ```
   `--test-push` sends a real push through the configured keys to every
   stored subscription and reports how many the push service accepted —
   the same supported path as a real approval, no grant involved.

3. **Subscribe (human, once per browser):** open the confirmd pending
   page → "Enable notifications". The browser's PushManager subscribes
   with the server's VAPID public key (served at `/api/push/config` —
   public by design), and the subscription (endpoint + `p256dh` + `auth`)
   is POSTed to `/api/push/subscribe`. The button only appears when the
   browser supports push and the server reports it enabled. On
   iPhone/iPad the page says *"add this page to your home screen, then
   open it from there"* instead — iOS only exposes Web Push to
   home-screen-installed pages.
   A denied browser permission shows a recovery hint: allow
   notifications for the site in the browser's site settings, then retry.

4. **Notify (automatic):** when swapd files an approval
   (`swap_addon._file_approval`), `_push_notify` fires
   `PushSender.default().notify_approval(item)` on a **daemon thread** —
   never on the mitmproxy flow thread, so a dead push service can't stall
   the agent's request (15s timeout × N subscriptions). One encrypted
   push per stored subscription. The service worker (`/sw.js`) shows the
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
  double-notify. **Idempotency does NOT fire on total transient
  failure:** if every send raised or returned a retryable error, the
  approval is deliberately left unmarked — marking it would silently drop
  the notification (the error is logged loudly instead). There is no
  retry path yet (see H14).
- **Race safety:** the subscription store and the notified log are
  mutated from two processes (confirmd's ThreadingHTTPServer and
  mitmproxy's swap_addon) and concurrent threads, so mutations hold an
  exclusive `fcntl.flock` sidecar lock (`<path>.lock`) around the
  load-modify-save — atomic `os.replace` alone doesn't prevent a stale
  read from dropping a subscription.
- **Lock-screen exposure:** the encrypted payload carries the approval
  summary — the same text the page already shows — which means the
  summary is visible on the device's lock screen when the notification
  fires. Operators who consider approval metadata sensitive should know
  this is inherent to lock-screen notifications, not a leak.
- **Notification dismissal:** answering an approval (approve/deny) closes
  that approval's notification on the device, so a stale notification
  can't tap through to an already-answered page.
- **Icons:** the service worker posts text-only notifications (no
  `icon`/`badge`) — the browser renders its own default. Custom icons are
  a follow-up, not this slice.
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
  screen; the status line says so explicitly (the button stays hidden).
- Custom notification icon/badge in the service worker (currently
  text-only; browser renders its own default).
